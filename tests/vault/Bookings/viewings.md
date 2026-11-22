---
title: Регламент бронювання переглядів
tags: [smartlease, bookings, viewings, antispam]
source: SmartLease Bookings Spec v1.0
updated: 2026-11-15
---

# Регламент бронювання переглядів

## Анти-спам ліміт
Авторизований користувач з роллю Tenant може подати не більше 3 заявок на перегляд житла протягом 24 годин. Оголошення має перебувати у статусі Active, інакше API повертає 400 Bad Request або 429 Too Many Requests.
