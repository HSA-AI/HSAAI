# SAP Integration Guide

This document defines the HSAAI integration approach for SAP S/4HANA and SAP Business ByDesign.

## Principles
- Read-only first.
- No direct user bypass of SAP permissions.
- All requests pass through HSAAI Permission Engine and Audit Logs.
- OData/REST connectors are disabled until approved endpoints and service accounts are provided by IT/SAP teams.

## Required Information
| Item | Description |
|---|---|
| Base URL | Internal SAP endpoint |
| Auth method | OAuth2 / Basic / SSO token |
| Service account | Read-only account |
| Scopes | Approved business entities |
| Audit owner | Responsible team |
