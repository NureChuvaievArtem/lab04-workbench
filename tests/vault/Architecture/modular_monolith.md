---
title: Межі модульного моноліту SmartLease
tags: [smartlease, architecture, modules, dotnet]
source: SmartLease Architecture Spec v1.0
updated: 2026-11-15
---

# Межі модульного моноліту SmartLease

## Ізоляція модулів
Модулі Properties, Bookings, Leases та Finance спілкуються лише через публічні контракти та доменні події. Прямі SQL JOIN між схемами різних модулів заборонені; кожен модуль має власні DTO, валідатори FluentValidation і перевірки авторизації Tenant/Landlord.
