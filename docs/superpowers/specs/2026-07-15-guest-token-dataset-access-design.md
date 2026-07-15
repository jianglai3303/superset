# Design: Dataset Access Check in `guest_token_sso`

**Date:** 2026-07-15  
**File:** `docker/pythonpath_dev/superset_config.py`  
**Endpoint:** `POST /api/v1/guest/guest_token_sso`

---

## Problem

The `guest_token_sso` endpoint currently grants a guest token to any valid Keycloak user without verifying whether that user's Superset roles grant them access to the datasets used by the requested dashboards. A user could receive a token for a dashboard whose underlying data they are not authorized to see.

---

## Goal

Before issuing the guest token, verify that the user's Superset roles include `datasource_access` (or `all_datasource_access`) for **every** dataset linked to the requested dashboards. If any dataset is inaccessible, return a `403` with a detailed error listing the denied datasets. All existing logic (RLS, embedded ID validation, JWT decode) is left unchanged.

---

## Data Model Chain

```
EmbeddedDashboard.uuid (input)
  └── EmbeddedDashboard.dashboard_id
        └── Dashboard.slices  (via dashboard_slices junction)
              └── Slice.datasource_id + datasource_type == "table"
                    └── SqlaTable.perm  (e.g. "[mydb].[sales](id:3)")
```

Access is granted if, for a given `SqlaTable.perm`, at least one of the user's role IDs appears in `ab_permission_view_role` joined to a `PermissionView` where `Permission.name == "datasource_access"` and `ViewMenu.name == <dataset.perm>`.

---

## Insertion Point

Inserted **after** user lookup and role extraction, **before** RLS rule query and token creation:

```
decode JWT
→ validate embedded dashboard UUIDs
→ lookup user + extract roles
→ [NEW] dataset access check  ← inserted here
→ build RLS rules
→ create_guest_access_token
```

---

## Primary Approach: Direct ORM Query (Option A)

Query FAB's permission tables directly using the user's role IDs. No Flask context manipulation.

### Steps

1. Extract `role_ids = [role.id for role in user.roles]`
2. Check `all_datasource_access`: query `ab_permission_view` where `Permission.name == "all_datasource_access"` and `PermissionView` is linked to any of `role_ids`. If found → skip further checks, all datasets accessible.
3. Collect datasets: from the already-fetched embedded dashboard IDs, load `Dashboard` objects, iterate `dashboard.slices`, collect unique `SqlaTable` objects where `slice.datasource_type == "table"`.
4. Collect accessible dataset perms: query `ViewMenu.name` values where `Permission.name == "datasource_access"` and `PermissionView` is linked to any of `role_ids`. Result is a set of perm strings.
5. Diff: datasets whose `perm` is not in the accessible set → denied list.
6. If denied list is non-empty, return:
   ```json
   {
     "error": "User does not have access to required datasets",
     "denied_datasets": [
       {"id": 3, "name": "sales", "schema": "public"}
     ]
   }
   ```
   HTTP status `403`.

### Why this works without `g.user`

The check is a pure DB query against `ab_permission`, `ab_view_menu`, `ab_permission_view`, and `ab_permission_view_role` using the user's role IDs — no Flask session or `g.user` involved.

---

## Backup Plan B: Temporarily swap `g.user`

If the FAB association table (`assoc_permissionview_role`) is not importable or the schema differs:

```python
from flask import g as flask_g
original_user = flask_g.user
flask_g.user = user
try:
    for ds in datasets.values():
        if not sm.can_access_datasource(ds):
            denied.append(...)
finally:
    flask_g.user = original_user
```

**Trade-off:** Works correctly only in a single-threaded context (dev server with `--with-threads` uses thread-local `g`, so this is safe per-request). Reuses Superset's own access logic.

---

## Backup Plan C: Role permission string matching via FAB

```python
role_perms = set()
for role in user.roles:
    for pvm in role.permissions:
        role_perms.add((pvm.permission.name, pvm.view_menu.name))

has_all = ("all_datasource_access", "all_datasource_access") in role_perms
for ds in datasets.values():
    if not has_all and ("datasource_access", ds.perm) not in role_perms:
        denied.append(...)
```

**Trade-off:** Loads all role permissions into memory via ORM lazy-loading. Simpler code but potentially many DB round-trips if roles have many permissions.

---

## Error Response Format

```json
HTTP 403
{
  "error": "User does not have access to required datasets",
  "denied_datasets": [
    {
      "id": 3,
      "name": "sales_data",
      "schema": "public"
    }
  ]
}
```

`id` is the `SqlaTable.id`, `name` is `SqlaTable.table_name`, `schema` is `SqlaTable.schema`.

---

## What Is Not Changed

- JWT decode and validation
- Embedded dashboard UUID existence check
- User lookup
- RLS rule collection and inclusion in the token
- Guest token creation

---

## Implementation Order

1. Add dataset access check block after `roles = [role.name for role in user.roles]`
2. Try Option A (direct ORM query)
3. If import error or query fails, fall back to Option C (role permission iteration), then Option B (g.user swap) as last resort
4. Restart Superset and test with a user whose role lacks dataset access
