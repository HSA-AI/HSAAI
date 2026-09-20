import { describe, it, expect } from "vitest";
import { can, getPermissions, ENTERPRISE_ROLES } from "../rbac";

describe("RBAC Module", () => {
  describe("ENTERPRISE_ROLES", () => {
    it("should define all expected enterprise roles", () => {
      expect(ENTERPRISE_ROLES).toContain("hsaai_admin");
      expect(ENTERPRISE_ROLES).toContain("knowledge_admin");
      expect(ENTERPRISE_ROLES).toContain("document_reviewer");
      expect(ENTERPRISE_ROLES).toContain("document_uploader");
      expect(ENTERPRISE_ROLES).toContain("department_manager");
      expect(ENTERPRISE_ROLES).toContain("ai_user");
      expect(ENTERPRISE_ROLES).toContain("auditor");
    });

    it("should have exactly 7 enterprise roles", () => {
      expect(ENTERPRISE_ROLES).toHaveLength(7);
    });
  });

  describe("can()", () => {
    it("should grant all permissions to hsaai_admin", () => {
      expect(can("any:permission", ["hsaai_admin"])).toBe(true);
      expect(can("admin:delete", ["hsaai_admin"])).toBe(true);
      expect(can("knowledge:admin", ["hsaai_admin"])).toBe(true);
    });

    it("should grant knowledge permissions to knowledge_admin", () => {
      const roles = ["knowledge_admin"];
      expect(can("knowledge:admin", roles)).toBe(true);
      expect(can("knowledge:read", roles)).toBe(true);
      expect(can("knowledge:write", roles)).toBe(true);
      expect(can("knowledge:review", roles)).toBe(true);
      expect(can("knowledge:delete", roles)).toBe(true);
      expect(can("audit:read", roles)).toBe(true);
    });

    it("should deny unauthorized permissions", () => {
      const roles = ["document_uploader"];
      expect(can("knowledge:admin", roles)).toBe(false);
      expect(can("admin:delete", roles)).toBe(false);
    });

    it("should grant chat access to ai_user", () => {
      expect(can("chat:write", ["ai_user"])).toBe(true);
      expect(can("knowledge:read", ["ai_user"])).toBe(true);
      expect(can("knowledge:admin", ["ai_user"])).toBe(false);
    });

    it("should grant read access to auditor", () => {
      const roles = ["auditor"];
      expect(can("knowledge:read", roles)).toBe(true);
      expect(can("audit:read", roles)).toBe(true);
      expect(can("analytics:read", roles)).toBe(true);
      expect(can("knowledge:write", roles)).toBe(false);
    });

    it("should handle multiple roles with OR logic", () => {
      const roles = ["ai_user", "document_reviewer"];
      expect(can("chat:write", roles)).toBe(true);    // from ai_user
      expect(can("knowledge:review", roles)).toBe(true); // from document_reviewer
      expect(can("knowledge:admin", roles)).toBe(false); // from neither
    });

    it("should handle empty roles array", () => {
      expect(can("knowledge:read", [])).toBe(false);
      expect(can("any:permission", [])).toBe(false);
    });

    it("should handle unknown role", () => {
      expect(can("knowledge:read", ["unknown_role"])).toBe(false);
    });
  });

  describe("getPermissions()", () => {
    it("should return sorted permissions for a role", () => {
      const perms = getPermissions(["knowledge_admin"]);
      expect(perms).toContain("knowledge:admin");
      expect(perms).toContain("knowledge:read");
      expect(perms).toContain("audit:read");
      // Should be sorted
      for (let i = 1; i < perms.length; i++) {
        expect(perms[i] >= perms[i - 1]).toBe(true);
      }
    });

    it("should deduplicate permissions across roles", () => {
      const perms = getPermissions(["ai_user", "document_uploader"]);
      const unique = new Set(perms);
      expect(perms.length).toBe(unique.size);
    });

    it("should not include wildcard * in permissions", () => {
      const perms = getPermissions(["hsaai_admin"]);
      expect(perms).not.toContain("*");
    });

    it("should return empty array for empty roles", () => {
      expect(getPermissions([])).toEqual([]);
    });
  });
});
