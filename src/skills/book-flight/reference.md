# Flight Booking Reference

This document contains supplementary information for the book-flight skill, including error handling strategies, best practices, and conversation examples.

## Error Handling

### Common Issues and Solutions

#### 1. No Flights Available

When no flights are found for the requested route/date:

**Diagnosis:**
```bash
# Check if the route exists
uv run scripts/search_flights.py --from "CITY" --to "CITY" --date "YYYY-MM-DD" --json
```

**Solutions:**
- Suggest alternative dates (±1-2 days from original request)
- Suggest nearby airports (e.g., if Beijing unavailable, try Tianjin)
- Check for different cabin classes (business class may have availability when economy is sold out)
- Recommend booking further in advance for popular routes

**Example Response:**
```
抱歉，您选择的日期暂无直飞航班。以下是一些替代方案：
1. 提前/延后一天出发（1月14日或1月16日有航班）
2. 选择经停航班（经上海转机）
3. 尝试其他舱位（商务舱仍有余票）
```

#### 2. Invalid Date Errors

**Common Causes:**
- Departure date is in the past
- Return date is before departure date
- Date format incorrect (should be YYYY-MM-DD)
- Booking too close to departure (some airlines require 2+ hours advance)

**Validation Rules:**
```python
# Date validation logic
departure_date >= current_date + timedelta(hours=2)  # Minimum lead time
return_date > departure_date  # For round trips
```

**Example Response:**
```
日期验证失败：
- 出发日期必须是未来的日期
- 返程日期必须晚于出发日期
- 建议至少提前2小时预订

请重新选择日期。
```

#### 3. Route Not Found

**Diagnosis Steps:**
1. Verify city/airport names are spelled correctly
2. Check if the route is serviced by any airline
3. Determine if connecting flights are needed

**Solutions:**
- Correct spelling/naming issues
- Suggest hub airports for connections
- Recommend alternative destinations

**Supported Cities:**
| City | Airport Code | Airport Name |
|------|--------------|--------------|
| Beijing | PEK | Beijing Capital International Airport |
| Shanghai | PVG | Shanghai Pudong International Airport |
| Guangzhou | CAN | Guangzhou Baiyun International Airport |
| Shenzhen | SZX | Shenzhen Bao'an International Airport |
| Tokyo | NRT | Narita International Airport |
| Seoul | ICN | Incheon International Airport |
| Singapore | SIN | Singapore Changi Airport |
| Hong Kong | HKG | Hong Kong International Airport |
| New York | JFK | John F. Kennedy International Airport |
| Los Angeles | LAX | Los Angeles International Airport |
| London | LHR | London Heathrow Airport |
| Paris | CDG | Paris Charles de Gaulle Airport |

#### 4. Booking Confirmation Failures

**Common Causes:**
- Invalid passenger information format
- Missing required fields
- System timeout

**Required Passenger Fields:**
```json
{
  "name": "Full name as on ID/passport",
  "id_type": "passport|id_card",
  "id_number": "Document number",
  "nationality": "Country code",
  "date_of_birth": "YYYY-MM-DD",
  "gender": "M|F"
}
```

---

## Best Practices

### 1. Information Verification

**Always double-check before searching:**
- Confirm city names (Beijing vs Nanjing sounds similar)
- Verify dates (especially year for bookings near year-end)
- Clarify passenger count and types (adult/child/infant)

**Verification Checklist:**
```
□ Departure city confirmed
□ Destination city confirmed  
□ Date(s) verified (format: YYYY-MM-DD)
□ Passenger count confirmed
□ Cabin class preference noted
□ Special requirements documented
```

### 2. Price Transparency

**Always display:**
- Base fare per person
- Taxes and fees (if applicable)
- Total price for all passengers
- Currency (CNY/USD/etc.)
- Baggage allowance included

**Price Breakdown Template:**
```
票价明细:
- 基础票价: ¥2,000 × 2人 = ¥4,000
- 机场建设费: ¥50 × 2人 = ¥100
- 燃油附加费: ¥200 × 2人 = ¥400
─────────────────────────
总计: ¥4,500
```

### 3. Offering Alternatives

When the first choice is unavailable, proactively suggest:
- Different dates (show price comparison)
- Different times (early morning often cheaper)
- Different airlines (compare services)
- Different cabin classes (upgrade opportunities)

### 4. Explicit Confirmation

**Critical confirmation points:**
1. Before searching (confirm all requirements)
2. After presenting options (confirm selection)
3. Before final booking (confirm all details)

**Never assume:**
- One-way vs round-trip
- Single passenger vs multiple
- Economy vs other classes

### 5. Time Zone Handling

**For international flights:**
- Always show local times for both departure and arrival
- Indicate time zone abbreviations (CST, JST, etc.)
- Note date changes for overnight flights

**Example:**
```
CA123 北京 → 东京
出发: 2024-01-15 08:00 (北京时间 CST)
到达: 2024-01-15 12:30 (东京时间 JST)
飞行时间: 3小时30分钟
```

---

## Conversation Flow Examples

### Example 1: Basic One-Way Booking

```
User: 我想订一张从北京到东京的机票

Agent: 好的，我来帮您查询北京到东京的航班。请问以下信息:
1. 您计划什么时候出发？
2. 需要往返机票还是单程？
3. 几位乘客？
4. 舱位偏好（经济舱/商务舱/头等舱）？

User: 1月15号出发，单程，1个人，经济舱

Agent: 收到，让我确认一下您的需求：
- 出发地：北京
- 目的地：东京  
- 出发日期：2025年1月15日
- 行程类型：单程
- 乘客：1位成人
- 舱位：经济舱

信息正确吗？我现在为您查询航班。

User: 对的

Agent: [执行 search_flights.py]

我为您找到以下航班选择：

| 航班 | 出发 | 到达 | 时长 | 价格 | 经停 |
|------|------|------|------|------|------|
| CA123 | 08:00 | 12:30 | 3h30m | ¥2,500 | 直飞 |
| MU456 | 14:00 | 18:45 | 3h45m | ¥2,200 | 直飞 |
| JL789 | 10:30 | 15:00 | 4h30m | ¥1,800 | 1次 |

请问您想选择哪个航班？

User: 第一个

Agent: 您选择的航班信息如下：
- 航班：CA123（中国国际航空）
- 出发：北京首都机场 (PEK) → 东京成田机场 (NRT)
- 时间：2025-01-15 08:00 - 12:30（当地时间）
- 乘客：1位成人
- 总价：¥2,500

请确认是否继续预订？
```

### Example 2: Round-Trip with Multiple Passengers

```
User: 帮我查一下下周末上海到香港的往返机票，两个大人一个小孩

Agent: 好的，让我先确认当前日期...[执行 get_current_time.py]

今天是2025年12月26日（周五），下周末是1月4日-5日。请问：
1. 具体出发日期是1月4日（周六）吗？
2. 返程日期是哪天？
3. 小孩的年龄是多少？（2岁以下为婴儿，2-12岁为儿童）
4. 舱位偏好？

User: 4号去6号回，小孩5岁，经济舱就行

Agent: 明白了，为您确认：
- 上海 → 香港：2025年1月4日
- 香港 → 上海：2025年1月6日
- 乘客：2位成人 + 1位儿童（5岁）
- 舱位：经济舱

正在查询...[执行 search_flights.py]

去程航班（1月4日 上海→香港）：
| 航班 | 出发 | 到达 | 时长 | 成人价 | 儿童价 |
|------|------|------|------|--------|--------|
| MU501 | 09:00 | 11:30 | 2h30m | ¥1,200 | ¥900 |
| CX882 | 14:00 | 16:25 | 2h25m | ¥1,500 | ¥1,125 |

返程航班（1月6日 香港→上海）：
| 航班 | 出发 | 到达 | 时长 | 成人价 | 儿童价 |
|------|------|------|------|--------|--------|
| MU502 | 12:30 | 15:00 | 2h30m | ¥1,100 | ¥825 |
| CX881 | 18:00 | 20:30 | 2h30m | ¥1,400 | ¥1,050 |

请选择去程和返程航班。
```

### Example 3: Handling No Availability

```
User: 明天北京到纽约的商务舱

Agent: [执行 get_current_time.py]
今天是2025年12月26日，您要查询12月27日北京到纽约的商务舱航班。

[执行 search_flights.py]

抱歉，12月27日北京直飞纽约的商务舱已售罄。我有以下建议：

1. **调整日期**：12月28日和29日仍有商务舱余票
2. **经停航班**：12月27日有经东京转机的航班，商务舱有票
3. **升级舱位**：头等舱12月27日仍有少量余票

您希望我查询哪个方案？
```

### Example 4: Clarification Needed

```
User: 订机票去日本

Agent: 好的，我来帮您预订去日本的机票。请问：

1. **出发城市**：您从哪个城市出发？
2. **目的地**：日本的哪个城市？（东京/大阪/名古屋等）
3. **出发日期**：您计划什么时候出发？
4. **行程类型**：单程还是往返？
5. **乘客人数**：几位乘客？
6. **舱位偏好**：经济舱/商务舱/头等舱？

User: 北京出发去东京，下个月10号，一个人，经济舱，单程

Agent: 收到！为您确认：
- 北京 → 东京
- 2025年1月10日
- 1位成人，经济舱，单程

正在为您查询航班...
```

---

## Script Reference

### get_current_time.py

**Purpose:** Get current date and time for booking context validation.

**Usage:**
```bash
uv run scripts/get_current_time.py
```

**Output:**
```json
{
  "current_datetime": "2025-12-26 11:55:48",
  "date": "2025-12-26",
  "time": "11:55:48",
  "weekday": "Friday",
  "timezone": "Local",
  "timestamp": 1766721348
}
```

### search_flights.py

**Purpose:** Search for available flights with various filters.

**Usage:**
```bash
uv run scripts/search_flights.py --from "CITY" --to "CITY" --date "YYYY-MM-DD" [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--from` | Departure city (required) | - |
| `--to` | Destination city (required) | - |
| `--date` | Departure date YYYY-MM-DD (required) | - |
| `--return-date` | Return date for round trip | None |
| `--passengers` | Number of passengers | 1 |
| `--class` | Cabin class: economy/business/first | economy |
| `--json` | Output in JSON format | False |

**Examples:**
```bash
# Basic search
uv run scripts/search_flights.py --from "Beijing" --to "Tokyo" --date "2025-01-15"

# Round trip with options
uv run scripts/search_flights.py --from "Shanghai" --to "Singapore" \
    --date "2025-02-01" --return-date "2025-02-07" \
    --passengers 2 --class business

# JSON output for parsing
uv run scripts/search_flights.py --from "Beijing" --to "Seoul" \
    --date "2025-01-20" --json
```

### confirm_booking.py

**Purpose:** Generate booking confirmation (mock).

**Usage:**
```bash
uv run scripts/confirm_booking.py --flight "FLIGHT_NO" --date "YYYY-MM-DD" --passengers "JSON" [OPTIONS]
```

**Options:**
| Option | Description | Required |
|--------|-------------|----------|
| `--flight` | Flight number | Yes |
| `--date` | Flight date | Yes |
| `--passengers` | Passenger info as JSON | Yes |
| `--email` | Contact email | No |
| `--phone` | Contact phone | No |
| `--json` | Output in JSON format | No |

**Passenger JSON Format:**
```json
[
  {"name": "Zhang San", "meal": "Vegetarian"},
  {"name": "Li Si", "meal": "Standard"}
]
```

**Example:**
```bash
uv run scripts/confirm_booking.py \
    --flight "CA123" \
    --date "2025-01-15" \
    --passengers '[{"name": "Zhang San"}, {"name": "Li Si"}]' \
    --email "user@example.com" \
    --phone "13800138000"
```

