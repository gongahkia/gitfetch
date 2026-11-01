"""Offline planner overhead, excluding collection, image work and ANSI painting."""
from statistics import median
from timeit import repeat

from modern_fixtures import DIMENSIONS, REFERENCE, fixture

from gitfetch.layout import AvatarGeometry, Viewport, plan_profile

_, _, document = fixture()
for columns, rows in DIMENSIONS:
    viewport = Viewport(columns, rows)
    samples = repeat(lambda viewport=viewport: plan_profile(document, viewport, avatar=AvatarGeometry(96, 96),
                                          reference_date=REFERENCE), number=100, repeat=5)
    print(f"{columns}x{rows}: {median(samples) * 10:.3f} ms/plan (median of 5 batches of 100)")
