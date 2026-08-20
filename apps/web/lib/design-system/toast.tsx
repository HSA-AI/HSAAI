"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

type ToastType = "success" | "warning" | "danger" | "info";

interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  show: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({
  show: () => {},
});

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

export function ToastContainer({
  children,
}: {
  children: ReactNode;
}) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const show = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = crypto.randomUUID();

      setToasts((current) => [
        ...current,
        {
          id,
          message,
          type,
        },
      ]);

      window.setTimeout(() => {
        setToasts((current) =>
          current.filter((toast) => toast.id !== id),
        );
      }, 5000);
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ show }}>
      {children}

      <div
        className="ds-toast-container"
        aria-live="polite"
        aria-atomic="true"
      >
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function Toast({
  message,
  type = "info",
}: {
  message: string;
  type?: ToastType;
}) {
  return (
    <div
      className={`ds-toast ds-toast-${type}`}
      role="alert"
    >
      <span>{message}</span>
    </div>
  );
}
