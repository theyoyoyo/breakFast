# Kitchen Appliances Settings — Task Specification

> **Status: implemented.** This is the original pre-implementation spec, kept for context.
> The shipped version differs in places (e.g. only Stove is enabled by default). The
> source of truth is `backend/models/kitchen.py`.

## Summary

Add a "Kitchen" sub-page in Settings where users configure which kitchen appliances
they own. The owned appliance list is stored per-user and fed to the LLM suggestion
personas and the kitchen scheduler so they only suggest meals and prep plans the user
can actually make.

---

## User Experience

### Entry Point

In the Settings page, add a **"Kitchen"** button alongside the existing sub-page
buttons (Profile, Supplements, Health Rules, Ratings, Data Management). Clicking it
opens a new sub-page.

### Kitchen Sub-Page Layout

- Big square toggle boxes for each appliance, arranged in a grid (2-3 per row on
  mobile, more on desktop)
- Each box shows: appliance icon/emoji + name
- Tapping a box toggles it ON/OFF
- **ON state**: prominent background (e.g., accent color), clear visual indicator
- **OFF state**: muted/dimmed, clearly not selected
- All appliances start **enabled by default** — user disables what they don't have
- No add/remove appliance functionality — the list is fixed, like ingredient groups

### Design Notes

- Should feel consistent with the rest of the app (dark theme, soft rounded corners,
  same color palette from `styles/common.js`)
- Grid layout with responsive columns
- Instant save — toggling an appliance immediately persists (no save button needed)
- Similar interaction pattern to the supplement daily toggle in the Chat tab

---

## Fixed Appliance List

Start with these appliances. The list is fixed in code (like INGREDIENT_GROUPS) and
can be expanded in the future by editing two locations: backend model and frontend
component.

| Appliance | Emoji | Notes |
|---|---|---|
| Air Fryer | -- | Can hold multiple similar items simultaneously (e.g., onion rings + fries + spring rolls + frozen pastries in one batch) |
| Toaster | -- | Turkish-style, broader than a Western toaster |
| Stove | -- | Multiple burners can be used simultaneously |
| Oven | -- | Standard kitchen oven |
| Blender | -- | For smoothies, purees, etc. |
| (more TBD) | -- | User will add more appliances they can think of in a future session |

**Important:** Emoji selection and additional appliances (e.g., sandwich press,
electric kettle, waffle maker, etc.) should be discussed with the user before
implementation, similar to how ingredient group emojis were chosen iteratively.

---

## Backend

### Database

New table: `user_kitchen_appliances`

```sql
CREATE TABLE IF NOT EXISTS user_kitchen_appliances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    appliance_key   TEXT    NOT NULL,  -- e.g. 'air_fryer', 'stove', 'oven'
    enabled         INTEGER NOT NULL DEFAULT 1,  -- 1 = owned, 0 = not owned
    UNIQUE(user_id, appliance_key)
);
```

On first access, if no rows exist for a user, auto-populate all appliances as
enabled (default = user owns everything, they disable what they don't have).

### Model

Define a `KITCHEN_APPLIANCES` list in a backend model file (similar to
`INGREDIENT_GROUPS` in `backend/models/ingredient.py`). Each entry should have:
- `key` — stable identifier (snake_case, used in DB and scheduler)
- `name` — display name (Turkish, shown in UI)
- `emoji` — visual icon
- `scheduler_resource` — maps to the resource name used by `backend/services/scheduler.py`
- `notes` — behavioral notes for the scheduler (e.g., "multiple burners", "batch items")

### API Endpoints

New router: `backend/routers/kitchen.py` with prefix `/kitchen`

- `GET /kitchen/` — returns the full appliance list with per-user enabled/disabled status
- `PUT /kitchen/{appliance_key}` — toggle enabled/disabled for a single appliance
  - Request body: `{ "enabled": true/false }`
  - Response: updated appliance object

### Integration Points

1. **Suggestion persona** (`personas/dietitian.py`): inject the list of owned
   appliances into the prompt context, so the LLM only suggests meals the user can
   prepare with their equipment. Format like:
   ```
   Available kitchen appliances: Air Fryer, Stove (multiple burners), Toaster, Oven
   ```

2. **Shopping persona** (`personas/shopping.py`): same injection — don't suggest
   ingredients that require appliances the user doesn't have.

3. **Scheduler persona** (`personas/scheduler.py`): only decompose tasks for
   appliances the user owns. If the user doesn't have an air fryer, the scheduler
   should suggest stove/oven alternatives.

4. **Kitchen scheduler** (`services/scheduler.py`): the greedy scheduling algorithm
   should only use resources that map to owned appliances. Filter the resource list
   based on the user's kitchen config before scheduling.

5. **Context loader** (`services/context.py`): add a `load_kitchen_appliances(db, user_id)`
   helper that returns the owned appliance list, formatted for prompt injection.

---

## Frontend

### API

Add to `frontend/src/services/api.js`:
- `getKitchenAppliances()` — GET /kitchen/
- `toggleKitchenAppliance(key, enabled)` — PUT /kitchen/{key}

### Component

New component: `KitchenSettings.jsx` (or inline sub-page in `SettingsPanel.jsx`,
depending on complexity — follow the pattern used by other Settings sub-pages).

- Fetches appliance list on mount
- Renders grid of toggle boxes
- Optimistic UI on toggle (revert on failure, like favorite heart toggle)
- Mirror the `KITCHEN_APPLIANCES` list from backend, or fetch it dynamically via
  the GET endpoint (preferred — single source of truth)

### Styles

New file `KitchenSettings.styles.js` (or extend `SettingsPanel.styles.js`).
Grid layout with big square boxes. Use the app's existing color variables.

---

## Scheduler Updates

The current scheduler specification in `CLAUDE.md` has a hardcoded "Available
Resources" list. Once this feature is implemented:

1. Remove the hardcoded resource list from the scheduler spec
2. The scheduler reads the user's owned appliances at runtime
3. Air fryer behavior: can batch multiple similar items simultaneously (already noted
   in the appliance model)
4. Stove behavior: multiple burners available simultaneously (already noted)
5. "Hands" resource remains implicit — always available, not a configurable appliance

---

## Testing

### Backend Tests

- `test_kitchen_list_default` — first GET returns all appliances enabled
- `test_kitchen_toggle_off` — disable an appliance, verify GET reflects it
- `test_kitchen_toggle_on` — re-enable, verify
- `test_kitchen_invalid_key` — PUT with unknown key returns 404
- `test_kitchen_per_user_isolation` — two users have independent configs

### Frontend Tests

- Component renders all appliances
- Toggle updates state optimistically

---

## Open Questions (Discuss Before Implementation)

1. **Full appliance list** — user said "other stuff that I don't remember right now".
   Before starting, ask the user to finalize the complete list. Candidates to discuss:
   - Sandwich press / tost makinesi
   - Electric kettle / su ısıtıcı
   - Waffle maker
   - Egg cooker
   - French press / moka pot / cezve
   - Microwave
   - Çay makinesi (Turkish tea machine)

2. **Emoji selection** — needs iterative discussion like ingredient groups.

3. **Appliance-specific notes** — some appliances have special scheduling behavior
   (air fryer batching, stove multi-burner). Should these notes be stored in the DB
   or kept in code? Recommend: keep in code (the `KITCHEN_APPLIANCES` model), since
   they're behavioral rules, not user data.

4. **Default state** — all enabled by default is the current plan. Confirm this is
   right (vs. starting with a minimal set and asking user to enable).
