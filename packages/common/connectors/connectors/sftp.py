"""
موصل SFTP / FTP لمنصة HSAAI
============================
يتيح هذا الموصل الوصول إلى خوادم SFTP عبر مكتبة paramiko.

الإجراءات المدعومة:
    - list_files    : سرد الملفات والمجلدات في مسار محدد
    - download_file : تنزيل ملف من الخادم (محتوى base64)
    - upload_file   : رفع ملف إلى الخادم (محتوى base64)
    - delete_file   : حذف ملف من الخادم
    - mkdir         : إنشاء مجلد على الخادم

كما يدعم search() للبحث في أسماء الملفات (recursive مع حد عمق).

ملاحظات:
    - مكتبة paramiko متزامنة، لذا يُغلّف الموصل استدعاءاتها بـ asyncio.to_thread.
    - إذا لم تكن paramiko مثبتة، يبقى الموصل قابلاً للاستيراد لكنه يرفع
      ConnectorError عند connect().
    - يدعم مصادقة كلمة المرور ومصادقة المفتاح الخاص (RSA/Ed25519).

الاستخدام:
    cfg = ConnectorConfig(
        name="sftp",
        display_name="Corporate SFTP",
        category="Files",
        base_url="sftp://sftp.corp.local:22",
        auth_strategy=AuthStrategy.BASIC,
        secrets={
            "username": "svc-sftp",
            "password": "...",
            # أو: "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----...",
            # واختياريًا: "private_key_passphrase": "..."
        },
    )
    connector = SFTPConnector(cfg)
    await connector.connect()
    files = await connector.call("list_files", path="/inbox")
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import stat
import time
from typing import Any, Optional

from packages.common.connectors import (
    AuthStrategy,
    BaseConnector,
    ConnectorAuthenticationError,
    ConnectorConfig,
    ConnectorError,
    HealthResult,
    HealthStatus,
    connector,
)

logger = logging.getLogger(__name__)

# محاولة استيراد paramiko مع fallback أنيق
try:
    import paramiko
    from paramiko import (
        SSHClient as ParamikoSSHClient,
        AutoAddPolicy as ParamikoAutoAddPolicy,
        RejectPolicy as ParamikoRejectPolicy,
    )
    from paramiko.ssh_exception import (
        AuthenticationException as ParamikoAuthException,
        SSHException as ParamikoSSHException,
        BadHostKeyException as ParamikoBadHostKeyException,
    )
    _PARAMIKO_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive
    paramiko = None  # type: ignore[assignment]
    ParamikoSSHClient = None  # type: ignore[assignment]
    ParamikoAutoAddPolicy = None  # type: ignore[assignment]
    ParamikoRejectPolicy = None  # type: ignore[assignment]
    ParamikoAuthException = Exception  # type: ignore[assignment]
    ParamikoSSHException = Exception  # type: ignore[assignment]
    ParamikoBadHostKeyException = Exception  # type: ignore[assignment]
    _PARAMIKO_AVAILABLE = False
    logger.warning(
        "sftp: مكتبة paramiko غير مثبتة — الموصل قابل للاستيراد "
        "لكن لن يعمل حتى تُثبت: pip install paramiko",
    )


@connector("sftp", version="1.0.0", category="Files")
class SFTPConnector(BaseConnector):
    """موصل SFTP عبر paramiko مع تشغيل async عبر to_thread."""

    #: المنفذ الافتراضي لـ SSH/SFTP
    DEFAULT_PORT: int = 22

    #: الإجراءات المدعومة
    SUPPORTED_ACTIONS: tuple[str, ...] = (
        "list_files",
        "download_file",
        "upload_file",
        "delete_file",
        "mkdir",
    )

    #: حد عمق البحث العودي الافتراضي
    DEFAULT_SEARCH_MAX_DEPTH: int = 3

    # ───────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────────────
    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # paramiko لا يستخدم HTTP — نُلغي العميل httpx
        self._client = None  # type: ignore[assignment]

        self._username: str = self._get_secret("username", "")
        self._password: str = self._get_secret("password", "")
        self._private_key_pem: str = self._get_secret("private_key", "")
        self._private_key_passphrase: str = self._get_secret(
            "private_key_passphrase", "",
        )
        # استخراج host و port من base_url بصيغة sftp://host:port
        self._host: str = self._parse_host()
        self._port: int = (
            int(getattr(self.config, "port", 0) or 0) or self._parse_port()
            or self.DEFAULT_PORT
        )
        # سلوك التحقق من host key
        self._host_key_policy: str = getattr(
            self.config, "host_key_policy", "auto_add",
        )
        self._known_hosts_file: Optional[str] = getattr(
            self.config, "known_hosts_file", None,
        )
        # مهلات
        self._timeout: float = float(getattr(self.config, "connect_timeout", 10.0))
        # عميل paramiko
        self._ssh_client: Any = None  # paramiko.SSHClient
        self._sftp_client: Any = None  # paramiko.SFTPClient
        # الدليل الرئيسي الافتراضي
        self._default_path: str = getattr(self.config, "default_path", "/")

    def _get_secret(self, key: str, default: str = "") -> str:
        """استرجاع سر من config.secrets بأمان."""
        secret = self.config.secrets.get(key)
        if secret is None:
            return default
        try:
            return secret.get_secret_value()
        except Exception:
            return default

    def _parse_host(self) -> str:
        """استخراج اسم الخادم من base_url بصيغة sftp://host:port."""
        url = self.config.base_url or ""
        if "://" in url:
            url = url.split("://", 1)[1]
        if "@" in url:
            # إزالة user@ إن وُجد
            url = url.split("@", 1)[1]
        if "/" in url:
            url = url.split("/", 1)[0]
        if ":" in url:
            url = url.split(":", 1)[0]
        return url

    def _parse_port(self) -> int:
        """استخراج المنفذ من base_url."""
        url = self.config.base_url or ""
        if "://" in url:
            url = url.split("://", 1)[1]
        if "@" in url:
            url = url.split("@", 1)[1]
        if "/" in url:
            url = url.split("/", 1)[0]
        if ":" in url:
            port_str = url.split(":", 1)[1]
            try:
                return int(port_str)
            except ValueError:
                return 0
        return 0

    # ───────────────────────────────────────────────────────────────────
    #  Connect / Disconnect (override — لا HTTP)
    # ───────────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """تهيئة الموصل: إنشاء اتصال SSH وفتح جلسة SFTP."""
        from packages.common.connectors.base import ConnectorState
        if self.state == ConnectorState.CONNECTED:
            return
        self.state = ConnectorState.INITIALIZING
        try:
            await self.authenticate()
            self.state = ConnectorState.CONNECTED
            logger.info(
                "sftp: تم الاتصال بـ %s:%d كـ %s", self._host, self._port, self._username,
            )
            self._start_health_check()
        except Exception as e:
            self.state = ConnectorState.ERROR
            logger.error("sftp: فشل الاتصال: %s", e)
            raise

    async def disconnect(self) -> None:
        """إغلاق اتصال SFTP وSSH."""
        from packages.common.connectors.base import ConnectorState
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except Exception:
                pass
            self._health_task = None
        if self._sftp_client is not None:
            try:
                await asyncio.to_thread(self._sftp_client.close)
            except Exception as exc:
                logger.warning("sftp: خطأ أثناء إغلاق SFTP: %s", exc)
            finally:
                self._sftp_client = None
        if self._ssh_client is not None:
            try:
                await asyncio.to_thread(self._ssh_client.close)
                logger.info("sftp: تم إغلاق اتصال SSH")
            except Exception as exc:
                logger.warning("sftp: خطأ أثناء إغلاق SSH: %s", exc)
            finally:
                self._ssh_client = None
        self.state = ConnectorState.DISCONNECTED

    # ───────────────────────────────────────────────────────────────────
    #  Authentication
    # ───────────────────────────────────────────────────────────────────
    async def authenticate(self) -> None:
        """إنشاء اتصال SSH مُصادَق مع خادم SFTP.

        يدعم:
          - مصادقة كلمة المرور (إن وُجد password).
          - مصادقة المفتاح الخاص (إن وُجد private_key PEM).
        يفتح جلسة SFTP بعد نجاح المصادقة.

        Raises:
            ConnectorAuthenticationError: عند فقدان البيانات أو فشل المصادقة.
            ConnectorError: إذا لم تكن paramiko متوفرة.
        """
        if not _PARAMIKO_AVAILABLE:
            raise ConnectorError(
                "sftp: مكتبة paramiko غير مثبتة. ثبّتها: pip install paramiko",
            )
        if not self._host or not self._username:
            raise ConnectorAuthenticationError(
                "sftp: host و username مطلوبان للاتصال",
            )
        if not self._password and not self._private_key_pem:
            raise ConnectorAuthenticationError(
                "sftp: يجب توفير password أو private_key للمصادقة",
            )

        # بناء عميل SSH
        ssh = ParamikoSSHClient()
        if self._host_key_policy == "reject":
            ssh.set_missing_host_key_policy(ParamikoRejectPolicy())
        else:
            ssh.set_missing_host_key_policy(ParamikoAutoAddPolicy())
        if self._known_hosts_file:
            try:
                ssh.load_host_keys(self._known_hosts_file)
            except Exception as exc:
                logger.warning(
                    "sftp: تعذّر تحميل known_hosts '%s': %s",
                    self._known_hosts_file, exc,
                )

        # بناء قائمة look_for_keys تلقائيًا عند عدم تمرير private_key
        look_for_keys = bool(self._private_key_pem)
        allow_agent = bool(self._private_key_pem)

        # محاولة الاتصال
        try:
            await asyncio.to_thread(
                ssh.connect,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password or None,
                pkey=self._load_private_key(),
                timeout=self._timeout,
                look_for_keys=look_for_keys,
                allow_agent=allow_agent,
            )
        except ParamikoAuthException as exc:
            raise ConnectorAuthenticationError(
                f"sftp: فشل المصادقة مع {self._host}:{self._port}: {exc}",
            ) from exc
        except ParamikoBadHostKeyException as exc:
            raise ConnectorAuthenticationError(
                f"sftp: host key غير مطابقة لـ {self._host}: {exc}",
            ) from exc
        except ParamikoSSHException as exc:
            raise ConnectorAuthenticationError(
                f"sftp: خطأ SSH أثناء الاتصال بـ {self._host}:{self._port}: {exc}",
            ) from exc
        except Exception as exc:
            raise ConnectorAuthenticationError(
                f"sftp: فشل الاتصال بـ {self._host}:{self._port}: {exc}",
            ) from exc

        self._ssh_client = ssh

        # فتح جلسة SFTP
        try:
            self._sftp_client = await asyncio.to_thread(ssh.open_sftp)
        except ParamikoSSHException as exc:
            await asyncio.to_thread(ssh.close)
            self._ssh_client = None
            raise ConnectorAuthenticationError(
                f"sftp: فشل فتح جلسة SFTP: {exc}",
            ) from exc

        logger.info(
            "sftp: تم فتح جلسة SFTP بنجاح على %s:%d", self._host, self._port,
        )

    def _load_private_key(self) -> Any:
        """تحميل المفتاح الخاص من PEM string.

        يدعم RSA, DSS, ECDSA, Ed25519 تلقائيًا عبر paramiko.
        """
        if not self._private_key_pem:
            return None
        # تجربة أنواع المفاتيح المدعومة
        key_classes = (
            "Ed25519Key",
            "ECDSAKey",
            "RSAKey",
            "DSSKey",
        )
        last_exc: Optional[Exception] = None
        for cls_name in key_classes:
            cls = getattr(paramiko, cls_name, None)
            if cls is None:
                continue
            try:
                from io import StringIO
                return cls.from_private_key(
                    StringIO(self._private_key_pem),
                    password=self._private_key_passphrase or None,
                )
            except ParamikoSSHException as exc:
                last_exc = exc
                continue
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            logger.warning(
                "sftp: تعذّر تحميل المفتاح الخاص (%s) — سيتم تجاهله: %s",
                type(last_exc).__name__, last_exc,
            )
        return None

    async def _ensure_connected(self) -> None:
        """التأكد من أن اتصال SFTP ما زال حيًا."""
        if not _PARAMIKO_AVAILABLE:
            raise ConnectorError(
                "sftp: paramiko غير متوفرة. ثبّتها: pip install paramiko",
            )
        if self._ssh_client is None or self._sftp_client is None:
            raise ConnectorError(
                "sftp: الاتصال غير مهيأ — استدعِ connect() أولاً",
            )
        # فحص سريع للاتصال عبر استدعاء listdir على "/"
        try:
            def _check() -> None:
                # get_transport قد يطرح استثناء عند انقطاع الاتصال
                transport = self._ssh_client.get_transport()
                if transport is None or not transport.is_active():
                    raise ConnectorError("sftp: النقل غير نشط")
            await asyncio.to_thread(_check)
        except Exception as exc:
            logger.warning("sftp: الاتصال معطوب، محاولة إعادة الاتصال: %s", exc)
            await self.authenticate()

    # ───────────────────────────────────────────────────────────────────
    #  Health Check
    # ───────────────────────────────────────────────────────────────────
    async def health(self) -> HealthResult:
        """فحص صحة اتصال SFTP عبر استدعاء pwd و listdir('.')."""
        start = time.monotonic()
        try:
            if not _PARAMIKO_AVAILABLE:
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    connector=self.config.name,
                    latency_ms=0.0,
                    error="paramiko library not installed",
                )
            await self._ensure_connected()

            def _probe() -> str:
                # استدعاء بسيط للتحقق من فعالية SFTP
                return self._sftp_client.normalize(".")

            current_dir = await asyncio.to_thread(_probe)
            latency_ms = (time.monotonic() - start) * 1000
            return HealthResult(
                status=HealthStatus.HEALTHY,
                connector=self.config.name,
                latency_ms=latency_ms,
                details={
                    "host": self._host,
                    "port": self._port,
                    "username": self._username,
                    "current_dir": current_dir,
                    "probe": "normalize('.')",
                },
            )
        except Exception as exc:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                connector=self.config.name,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    #  SFTP Helpers (sync wrapped with to_thread)
    # ───────────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize_path(path: Optional[str], default: str = "/") -> str:
        """تطبيع مسار SFTP (لا يمكن أن يكون فارغًا)."""
        if not path or not str(path).strip():
            return default
        return str(path)

    def _stat_to_dict(self, attrs: Any) -> dict[str, Any]:
        """تحويل paramiko SFTPAttributes إلى dict قابل للتسلسل."""
        return {
            "size": attrs.st_size,
            "uid": attrs.st_uid,
            "gid": attrs.st_gid,
            "mode": attrs.st_mode,
            "permissions": oct(attrs.st_mode & 0o777) if attrs.st_mode else None,
            "is_dir": bool(stat.S_ISDIR(attrs.st_mode or 0)),
            "is_file": bool(stat.S_ISREG(attrs.st_mode or 0)),
            "is_symlink": bool(stat.S_ISLNK(attrs.st_mode or 0)),
            "mtime": attrs.st_mtime,
            "atime": attrs.st_atime,
        }

    # ───────────────────────────────────────────────────────────────────
    #  Search
    # ───────────────────────────────────────────────────────────────────
    async def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """البحث في أسماء الملفات في شجرة SFTP.

        يقوم بسرد تكراري (recursive) بدءًا من مسار محدد ويطابق أسماء الملفات
        جزئيًا (غير حساس لحالة الأحرف).

        Args:
            query: نص البحث.
            **kwargs:
                path (str): مسار البداية (افتراضيًا default_path).
                max_depth (int): أقصى عمق للبحث (افتراضيًا 3).
                top (int): أقصى عدد نتائج (افتراضيًا 100).
                files_only (bool): تضمين الملفات فقط لا المجلدات (افتراضيًا False).

        Returns:
            قائمة بنتائج البحث {path, name, size, is_dir}.
        """
        if not query or not query.strip():
            return []
        query_lower = query.strip().lower()
        path = self._normalize_path(kwargs.pop("path", self._default_path), self._default_path)
        max_depth = int(kwargs.pop("max_depth", self.DEFAULT_SEARCH_MAX_DEPTH))
        top = int(kwargs.pop("top", 100))
        files_only = bool(kwargs.pop("files_only", False))

        await self._ensure_connected()

        def _do() -> list[dict[str, Any]]:
            results: list[dict[str, Any]] = []

            def _walk(dir_path: str, depth: int) -> None:
                if depth > max_depth or len(results) >= top:
                    return
                try:
                    entries = self._sftp_client.listdir_attr(dir_path)
                except Exception as exc:
                    logger.debug("sftp: تعذّر سرد %s: %s", dir_path, exc)
                    return
                for entry in entries:
                    if len(results) >= top:
                        return
                    name = entry.filename
                    if query_lower in name.lower():
                        attr_dict = self._stat_to_dict(entry)
                        if files_only and not attr_dict["is_file"]:
                            continue
                        results.append({
                            "type": "file" if attr_dict["is_file"] else (
                                "symlink" if attr_dict["is_symlink"] else "dir"
                            ),
                            "path": f"{dir_path.rstrip('/')}/{name}",
                            "name": name,
                            "size": attr_dict["size"],
                            "is_dir": attr_dict["is_dir"],
                            "is_file": attr_dict["is_file"],
                            "mtime": attr_dict["mtime"],
                        })
                    # الغوص في المجلدات
                    if entry.st_mode and stat.S_ISDIR(entry.st_mode):
                        sub_path = f"{dir_path.rstrip('/')}/{name}"
                        _walk(sub_path, depth + 1)

            _walk(path, 0)
            return results
        try:
            return await asyncio.to_thread(_do)
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل search في '{path}': {exc}",
            ) from exc

    # ───────────────────────────────────────────────────────────────────
    #  Execute / Actions
    # ───────────────────────────────────────────────────────────────────
    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """تنفيذ إجراء مُسماً على SFTP.

        Raises:
            ConnectorError: عند طلب إجراء غير مدعوم.
        """
        handlers = {
            "list_files": self._list_files,
            "download_file": self._download_file,
            "upload_file": self._upload_file,
            "delete_file": self._delete_file,
            "mkdir": self._mkdir,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ConnectorError(
                f"sftp: إجراء غير معروف '{action}'. "
                f"الإجراءات المدعومة: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def _list_files(self, **kw: Any) -> dict[str, Any]:
        """سرد الملفات والمجلدات في مسار محدد.

        Args (via kwargs):
            path (str): المسار (افتراضيًا default_path).
        """
        path = self._normalize_path(kw.get("path"), self._default_path)
        await self._ensure_connected()

        def _do() -> list[dict[str, Any]]:
            try:
                entries = self._sftp_client.listdir_attr(path)
            except FileNotFoundError as exc:
                raise ConnectorError(
                    f"sftp: المسار غير موجود: {path}",
                ) from exc
            except PermissionError as exc:
                raise ConnectorError(
                    f"sftp: لا تملك صلاحية قراءة '{path}': {exc}",
                ) from exc
            files: list[dict[str, Any]] = []
            for entry in entries:
                attr_dict = self._stat_to_dict(entry)
                files.append({
                    "name": entry.filename,
                    "path": f"{path.rstrip('/')}/{entry.filename}",
                    "size": attr_dict["size"],
                    "is_dir": attr_dict["is_dir"],
                    "is_file": attr_dict["is_file"],
                    "is_symlink": attr_dict["is_symlink"],
                    "permissions": attr_dict["permissions"],
                    "mtime": attr_dict["mtime"],
                    "atime": attr_dict["atime"],
                    "uid": attr_dict["uid"],
                    "gid": attr_dict["gid"],
                })
            return files
        try:
            files = await asyncio.to_thread(_do)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل list_files في '{path}': {exc}",
            ) from exc
        return {"path": path, "count": len(files), "files": files}

    async def _download_file(self, **kw: Any) -> dict[str, Any]:
        """تنزيل ملف من خادم SFTP.

        Args (via kwargs):
            path (str): مسار الملف على الخادم (مطلوب).

        Returns:
            {"path": str, "name": str, "size": int, "content_type": str,
             "content_base64": str}.
        """
        path = kw.get("path")
        if not path or not str(path).strip():
            raise ConnectorError("sftp: download_file يتطلب 'path'")
        path = str(path)
        await self._ensure_connected()

        def _do() -> tuple[bytes, str, int]:
            # التحقق من وجود الملف وأنه ملف (ليس مجلدًا)
            try:
                attrs = self._sftp_client.stat(path)
            except FileNotFoundError as exc:
                raise ConnectorError(
                    f"sftp: الملف غير موجود: {path}",
                ) from exc
            if attrs.st_mode and stat.S_ISDIR(attrs.st_mode):
                raise ConnectorError(
                    f"sftp: المسار '{path}' هو مجلد وليس ملفًا",
                )
            # تنزيل المحتوى عبر open + read
            with self._sftp_client.file(path, mode="rb") as fh:
                fh.prefetch(attrs.st_size or 0)
                content = fh.read()
            name = path.rsplit("/", 1)[-1]
            return content, name, (attrs.st_size or len(content))

        try:
            content, name, size = await asyncio.to_thread(_do)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل download_file '{path}': {exc}",
            ) from exc

        content_b64 = base64.b64encode(content).decode("ascii")
        return {
            "path": path,
            "name": name,
            "size": size,
            "content_type": "application/octet-stream",
            "content_base64": content_b64,
        }

    async def _upload_file(self, **kw: Any) -> dict[str, Any]:
        """رفع ملف إلى خادم SFTP.

        Args (via kwargs):
            path (str): مسار الوجهة على الخادم (مطلوب).
            content_base64 (str): محتوى الملف مُرمَّز base64 (مطلوب).
            mode (str): صلاحيات الملف بالنظام الثماني (افتراضيًا '0644').

        Returns:
            {"path": str, "size": int, "uploaded": bool}.
        """
        path = kw.get("path")
        content_b64 = kw.get("content_base64")
        if not path or not content_base64:
            raise ConnectorError(
                "sftp: upload_file يتطلب 'path' و 'content_base64'",
            )
        mode_str = str(kw.get("mode", "0644"))
        try:
            mode_int = int(mode_str, 8)
        except (ValueError, TypeError) as exc:
            raise ConnectorError(
                f"sftp: mode غير صالح '{mode_str}' (متوقع octal مثل 0644)",
            ) from exc
        # فك ترميز المحتوى
        try:
            content = base64.b64decode(content_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ConnectorError(
                f"sftp: فشل فك ترميز base64: {exc}",
            ) from exc

        await self._ensure_connected()

        def _do() -> int:
            # استخدام file() مع mode 'wb' ثم chmod
            with self._sftp_client.file(path, mode="wb") as fh:
                fh.write(content)
            try:
                self._sftp_client.chmod(path, mode_int)
            except Exception as exc:
                logger.debug(
                    "sftp: تعذّر تطبيق chmod على %s: %s", path, exc,
                )
            return len(content)

        try:
            size = await asyncio.to_thread(_do)
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل upload_file '{path}': {exc}",
            ) from exc
        return {
            "path": path,
            "size": size,
            "mode": mode_str,
            "uploaded": True,
        }

    async def _delete_file(self, **kw: Any) -> dict[str, Any]:
        """حذف ملف من خادم SFTP.

        Args (via kwargs):
            path (str): مسار الملف (مطلوب).
        """
        path = kw.get("path")
        if not path or not str(path).strip():
            raise ConnectorError("sftp: delete_file يتطلب 'path'")
        path = str(path)
        await self._ensure_connected()

        def _do() -> bool:
            # التحقق من أنه ملف وليس مجلدًا
            try:
                attrs = self._sftp_client.stat(path)
            except FileNotFoundError as exc:
                raise ConnectorError(
                    f"sftp: الملف غير موجود: {path}",
                ) from exc
            if attrs.st_mode and stat.S_ISDIR(attrs.st_mode):
                raise ConnectorError(
                    f"sftp: المسار '{path}' هو مجلد — استخدم rmdir منفصل",
                )
            self._sftp_client.remove(path)
            return True

        try:
            await asyncio.to_thread(_do)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل delete_file '{path}': {exc}",
            ) from exc
        return {"path": path, "deleted": True}

    async def _mkdir(self, **kw: Any) -> dict[str, Any]:
        """إنشاء مجلد على خادم SFTP.

        Args (via kwargs):
            path (str): مسار المجلد (مطلوب).
            mode (str): صلاحيات المجلد بالنظام الثماني (افتراضيًا '0755').
            recursive (bool): إنشاء المسار الأبوي إن لزم (افتراضيًا False).
        """
        path = kw.get("path")
        if not path or not str(path).strip():
            raise ConnectorError("sftp: mkdir يتطلب 'path'")
        path = str(path)
        mode_str = str(kw.get("mode", "0755"))
        try:
            mode_int = int(mode_str, 8)
        except (ValueError, TypeError) as exc:
            raise ConnectorError(
                f"sftp: mode غير صالح '{mode_str}' (متوقع octal مثل 0755)",
            ) from exc
        recursive = bool(kw.get("recursive", False))
        await self._ensure_connected()

        def _do() -> bool:
            if recursive:
                # إنشاء كل مستوى من المسار
                parts = path.strip("/").split("/")
                current = ""
                for part in parts:
                    if not part:
                        continue
                    current = f"{current}/{part}"
                    try:
                        self._sftp_client.stat(current)
                    except FileNotFoundError:
                        self._sftp_client.mkdir(current, mode=mode_int)
            else:
                try:
                    self._sftp_client.mkdir(path, mode=mode_int)
                except FileNotFoundError as exc:
                    raise ConnectorError(
                        f"sftp: المسار الأبوي غير موجود لـ '{path}' "
                        f"(استخدم recursive=True): {exc}",
                    ) from exc
            return True

        try:
            await asyncio.to_thread(_do)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                f"sftp: فشل mkdir '{path}': {exc}",
            ) from exc
        return {"path": path, "mode": mode_str, "recursive": recursive, "created": True}

    # ───────────────────────────────────────────────────────────────────
    #  Metadata & Permissions
    # ───────────────────────────────────────────────────────────────────
    def metadata(self) -> dict[str, Any]:
        """إرجاع البيانات الوصفية للموصل."""
        return {
            "name": self.config.name,
            "display_name": self.config.display_name,
            "category": self.config.category,
            "version": self.config.version,
            "base_url": self.config.base_url,
            "auth_strategy": self.config.auth_strategy.value,
            "protocol": "SFTP (SSH File Transfer Protocol, paramiko)",
            "paramiko_available": _PARAMIKO_AVAILABLE,
            "capabilities": {
                "search": True,
                "execute": True,
                "sync": False,
                "write": True,
                "download": True,
                "upload": True,
                "delete": True,
            },
            "actions": list(self.SUPPORTED_ACTIONS),
            "host": self._host,
            "port": self._port,
            "username": self._username,
            "auth_method": (
                "private_key" if self._private_key_pem
                else "password" if self._password
                else "none"
            ),
            "host_key_policy": self._host_key_policy,
            "default_path": self._default_path,
        }

    def permissions(self) -> list[str]:
        """إرجاع الصلاحيات المطلوبة لاستخدام الموصل."""
        return self.config.required_permissions or [
            "connector:sftp:read",
            "connector:sftp:write",
            "files:read",
            "files:write",
            "files:delete",
        ]
