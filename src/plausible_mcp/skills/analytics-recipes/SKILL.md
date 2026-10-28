---
name: analytics-recipes
description: "Practical analysis recipes and diagnostic playbooks for traffic summaries, acquisition channels, landing pages, and growth trends."
---

# Plausible Analytics Recipes & Diagnostic Playbooks

Practical analysis sequences for agents answering questions about traffic, channels, and content.

## Recipe 1: 30-Day Executive Traffic Summary
**Goal**: Quick health check of total volume and engagement.
1. Call `get_aggregate_stats(site_id="yourdomain.com", date_range="30d")`.
2. Inspect `visitors`, `pageviews`, `bounce_rate`, and `visit_duration`.
3. Check `get_realtime_visitors(site_id="yourdomain.com")` to gauge immediate live activity.

## Recipe 2: Acquisition Channel Audit
**Goal**: Find where top traffic is coming from (search, direct, social, referral).
1. Call `get_breakdown(site_id="yourdomain.com", property_name="visit:source", limit=15)`.
2. For granular UTM campaign tracking: `get_breakdown(site_id="yourdomain.com", property_name="visit:campaign")`.
3. For medium classification: `get_breakdown(site_id="yourdomain.com", property_name="visit:medium")`.

## Recipe 3: Top Content & Landing Pages
**Goal**: Identify most-read articles and entrance points.
1. Call `get_breakdown(site_id="yourdomain.com", property_name="event:page", limit=20)`.
2. To find landing pages that drive visits: `get_breakdown(site_id="yourdomain.com", property_name="event:entry_page", limit=20)`.
3. To inspect where users leave: `get_breakdown(site_id="yourdomain.com", property_name="event:exit_page", limit=20)`.

## Recipe 4: Geography & Device Segmentation
**Goal**: Check user locale and client platform distribution.
1. Countries: `get_breakdown(site_id="yourdomain.com", property_name="visit:country", limit=10)`.
2. Devices: `get_breakdown(site_id="yourdomain.com", property_name="visit:device", limit=5)`.
3. Browsers: `get_breakdown(site_id="yourdomain.com", property_name="visit:browser", limit=10)`.
4. Operating Systems: `get_breakdown(site_id="yourdomain.com", property_name="visit:os", limit=10)`.

## Recipe 5: Day-over-Day Trends & Growth Patterns
**Goal**: Plot trendlines and detect traffic spikes or dips.
1. Call `get_timeseries(site_id="yourdomain.com", date_range="30d", interval="date")`.
2. Note any sudden spikes (e.g., Hacker News, product launch, newsletter send) or weekend drop-offs.
