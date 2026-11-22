---
title: Патерн Outbox для надійної доставки подій
tags: [smartlease, architecture, events, outbox]
source: SmartLease Architecture Spec v1.0
updated: 2026-11-15
---

# Патерн Outbox для надійної доставки подій

## Гарантії доставки та дедуплікація
У платформі SmartLease кожна міжмодульна подія публікується через транзакційну таблицю outbox_messages у PostgreSQL. Споживачі подій повинні вести таблицю idempotent_consumers для гарантії ідемпотентної обробки без дублювання бізнес-операцій.
