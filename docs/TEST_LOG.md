# Test Log

Failed tests / bugs found, and how each was fixed. (Real entries, newest last.)

## Phase 4 (synthetic data)
1. **Schema generator crash** - `ValueError: list.remove(x)`: I tried to remove a restricted table from
   the allowed list before it had been added. Fix: simply never add it.
2. **Mongo SQL-text renderer crash** - `NameError: name 's' is not defined` in `datagen/sqltext.py`
   (a dict comprehension used the wrong variable). Fix: iterate over `plan["sort"]` properly.
3. **Questions that dropped information** (found by reading samples, validator could NOT catch it):
   some question frames left out the selected columns / sort / limit that the plan contained.
   Fix: `compose()` now only uses frames that contain every piece the plan needs.
4. **Typo corrupted a value** (`test_every_generated_example_is_valid_and_values_are_in_question`):
   typo step changed `Elena` to `Eleena` inside a token. Fix: never apply a typo to a token containing a value.
5. **Value check was too loose** (`test_values_check_catches_a_mismatch`): `Pune` matched inside `Punee`.
   Fix: the check now needs exact word boundaries.
6. **Whitespace cleanup broke a value**: a "contains" value like `.jone` lost its space. Fix: substring
   values now use letters/digits only.
7. Grammar glitches found in samples ("the first 3 all doctors", "and its the diner is vip") - fixed.
8. Stray "?" after statements - fixed (only questions that start with a question word get "?").

Final: `pytest` -> 45 passed.
