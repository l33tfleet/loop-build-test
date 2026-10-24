"""Planet birthdays: an Earth age converted to each planet's years."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
import math


def context(state):
    age, periods = state["age"], state["periods"]
    birthdays = []
    age_error = None
    if age is not None:
        try:
            earth_age = float(age)
            if not math.isfinite(earth_age) or not 0 <= earth_age <= 120:
                raise ValueError
        except ValueError:
            age_error = "Enter a finite Earth age from 0 through 120."
        else:
            # Normalize signed zero so every zero result displays as 0.0.
            earth_age = earth_age or 0.0
            for planet in state["planets"]:
                name = planet["name"]
                # Earth's ratio is exactly one; avoid float round-trip rounding drift.
                years = earth_age if name == "Earth" else earth_age * periods["Earth"] / periods[name]
                birthdays.append({"name": name, "years": f"{years:.1f}"})
    return {"age_error": age_error, "birthdays": birthdays}
