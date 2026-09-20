# File Server ACL + RAG Integration Guide

HSAAI must respect Windows ACL permissions when indexing and answering from File Server or SharePoint documents.

## Rule
If a user cannot open a file in the source system, HSAAI must not expose its content through chat, RAG, snippets, or citations.
