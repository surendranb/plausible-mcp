# Plausible Analytics Overview & Methodology

Guide for AI agents interpreting website metrics through `plausible-mcp`.

## Privacy-First Architecture
Plausible is a lightweight, open-source, privacy-focused alternative to Google Analytics.
- No cookies are used.
- No personally identifiable information (PII) is collected.
- Unique visitors are counted per calendar day per site via a daily salted hash of IP address + User Agent.

## Metric Definitions
1. **Visitors (`visitors`)**:
   - Number of unique visitors to your site in the selected time range.
   - Note: For ranges > 1 day, sum of daily visitors may exceed overall unique visitors because return visitors are deduplicated across the entire period.
2. **Pageviews (`pageviews`)**:
   - Total count of pageview events tracked.
3. **Visits / Sessions (`visits`)**:
   - Distinct browsing sessions (a session ends after 30 minutes of inactivity).
4. **Bounce Rate (`bounce_rate`)**:
   - Percentage of visitors who visited only a single page on your site.
   - Calculated as: `(single_page_visits / total_visits) * 100`.
5. **Visit Duration (`visit_duration`)**:
   - Average session duration in seconds for visitors who visited more than one page.

## Supported Date Ranges & Periods
- `day` or `today`: Current day
- `7d`: Last 7 calendar days
- `30d`: Last 30 calendar days (default)
- `month`: Current calendar month
- `6mo`: Last 6 months
- `12mo`: Last 12 months
- Custom range: `YYYY-MM-DD,YYYY-MM-DD` (e.g. `2026-09-01,2026-09-30`)

## Error Handling Guide
- `[INPUT_FIXABLE]`: Check `site_id`, `property_name`, or date range formatting.
- `[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]`: Missing or invalid `PLAUSIBLE_API_KEY`. Prompt user to generate API key in Plausible Settings.
- `[TRANSIENT]`: Rate limit or network hiccup. Backoff and retry.
