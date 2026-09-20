# Windows Server / Active Directory Integration Guide

HSAAI should integrate with Windows Server Active Directory through Keycloak federation.

## Flow
Active Directory → Keycloak → HSAAI Auth Service → RBAC → Workspaces.

## Required Information
- LDAPS URL
- Base DN
- Bind DN and read-only bind password
- AD groups per department
- MFA policy
- Group-to-role mapping
