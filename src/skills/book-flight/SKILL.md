---
name: book-flight
description: Flight booking assistant that helps users search for flights, compare options, and complete bookings. Guides users through the standard operating procedure for booking flights.
---

# Flight Booking Guide

## Overview

This skill provides a standard operating procedure (SOP) for booking flights. It guides the agent through the complete flight booking process, from gathering requirements to confirming the booking.

## Standard Operating Procedure

### Step 1: Check Current Time

Before starting the booking process, verify the current date and time to ensure accurate scheduling.

```bash
uv run scripts/get_current_time.py
```

This helps establish:
- Current date for departure date validation
- Time zone awareness for international flights
- Lead time requirements (some bookings need minimum advance notice)

### Step 2: Gather Flight Requirements

Collect the following essential information from the user. If any information is missing, **ask the user to confirm**:

| Required Info | Description | Example |
|---------------|-------------|---------|
| Departure City | Origin airport/city | Beijing, Shanghai, New York |
| Destination City | Arrival airport/city | Tokyo, London, Los Angeles |
| Departure Date | When to depart | 2024-01-15 |
| Return Date (optional) | For round trips | 2024-01-20 |
| Number of Passengers | How many travelers | 1 adult, 2 children |
| Cabin Class | Service level | Economy, Business, First |

**Important**: Always confirm with the user if:
- Departure date is less than 24 hours away
- No return date specified (confirm if one-way is intended)
- Multiple passengers with different requirements

### Step 3: Search for Available Flights

Once requirements are confirmed, search for available flights:

```bash
uv run scripts/search_flights.py --from "DEPARTURE_CITY" --to "DESTINATION_CITY" --date "YYYY-MM-DD" [--return-date "YYYY-MM-DD"] [--passengers N] [--class economy|business|first]
```

Example:
```bash
uv run scripts/search_flights.py --from "Beijing" --to "Tokyo" --date "2024-01-15" --passengers 2 --class economy
```

### Step 4: Present Flight Options

After searching, present the flight options to the user in a clear format:

| Flight | Departure | Arrival | Duration | Price | Stops |
|--------|-----------|---------|----------|-------|-------|
| CA123 | 08:00 | 12:30 | 4h30m | ¥2,500 | Direct |
| MU456 | 14:00 | 18:45 | 4h45m | ¥2,200 | Direct |
| JL789 | 10:30 | 16:00 | 5h30m | ¥1,800 | 1 stop |

Include:
- Flight number and airline
- Departure and arrival times (with time zones for international)
- Total flight duration
- Price per person
- Number of stops
- Any notable features (meals, baggage allowance, etc.)

### Step 5: Confirm Selection

After user selects a flight:
1. Summarize the selected flight details
2. Confirm total price (including all passengers)
3. Review any special requirements (meals, seats, baggage)
4. Get explicit confirmation before proceeding

Example confirmation prompt:
```
您选择的航班信息如下:
- 航班: CA123 (中国国际航空)
- 出发: 北京首都机场 (PEK) → 东京成田机场 (NRT)
- 时间: 2024-01-15 08:00 - 12:30 (当地时间)
- 乘客: 2位成人
- 总价: ¥5,000

请确认是否继续预订？(是/否)
```

### Step 6: Complete Booking (Mock)

For actual booking, the system would:
1. Collect passenger details (names, ID/passport numbers)
2. Process payment
3. Generate booking confirmation

```bash
uv run scripts/confirm_booking.py --flight "FLIGHT_NUMBER" --date "YYYY-MM-DD" --passengers "PASSENGER_INFO"
```

## Quick Reference

| Task | Script | Description |
|------|--------|-------------|
| Check time | `get_current_time.py` | Get current date/time |
| Search flights | `search_flights.py` | Query available flights |
| Confirm booking | `confirm_booking.py` | Finalize reservation |

## Error Handling

**IMPORTANT**: When you encounter errors (e.g., "Unknown city", "No flights found", "Invalid date"), you MUST load the reference document for detailed solutions:

```
load_skill_reference("book-flight", "reference.md")
```

The reference document contains:
- **Supported Cities List** - All valid city names and airport codes
- **Error Solutions** - Step-by-step solutions for common issues
- **Alternative Suggestions** - How to offer alternatives when requests can't be fulfilled

## Additional Resources

For detailed information on error handling, best practices, conversation examples, and complete script documentation, load [reference.md](./reference.md) using `load_skill_reference`.

Contents include:
- **Error Handling** - Solutions for common issues (no flights, invalid dates, route not found)
- **Best Practices** - Information verification, price transparency, time zone handling
- **Conversation Examples** - Complete dialog flows for various booking scenarios
- **Script Reference** - Detailed usage and options for all scripts

