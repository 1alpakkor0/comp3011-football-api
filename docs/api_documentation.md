# Football Analytics API Documentation

## Overview

This project implements a RESTful API for analysing English Premier League football data.
The API allows users to query match statistics, league tables, team performance summaries, and match win probabilities.

The system is built using:

* **Django**
* **SQLite database**
* **REST-style HTTP endpoints**
* **Poisson probability model for match prediction**

Dataset source:
English Premier League match data (2020–2022 seasons).

Base URL (local):

```
http://localhost:8000
```

---

# API Endpoints

---

# 1 Health Check

### Endpoint

```
GET /api/health/
```

### Description

Simple endpoint used to verify that the API server is running correctly.

### Example Response

```json
{
  "status": "ok"
}
```

---

# 2 Teams

This endpoint manages football teams stored in the database.

Supports full **CRUD operations**.

---

## 2.1 List Teams

### Endpoint

```
GET /api/teams/
```

### Description

Returns a list of all teams stored in the database.

### Example Response

```json
{
  "count": 20,
  "teams": [
    {
      "id": 1,
      "name": "Arsenal"
    },
    {
      "id": 2,
      "name": "Chelsea"
    }
  ]
}
```

---

## 2.2 Create Team

### Endpoint

```
POST /api/teams/
```

### Request Body

```json
{
  "name": "Example FC"
}
```

### Example Response

```json
{
  "id": 21,
  "name": "Example FC"
}
```

### Status Codes

| Code | Meaning         |
| ---- | --------------- |
| 201  | Team created    |
| 400  | Invalid request |

---

## 2.3 Update Team

### Endpoint

```
PUT /api/teams/{id}/
```

### Example Request

```json
{
  "name": "Example FC Updated"
}
```

### Example Response

```json
{
  "id": 21,
  "name": "Example FC Updated"
}
```

---

## 2.4 Delete Team

### Endpoint

```
DELETE /api/teams/{id}/
```

### Example Response

```json
{
  "message": "Team deleted successfully"
}
```

---

# 3 League Table

### Endpoint

```
GET /api/analytics/table/
```

### Parameters

| Parameter | Description       |
| --------- | ----------------- |
| season    | Season identifier |

Example:

```
/api/analytics/table/?season=2021-2022
```

### Example Response

```json
{
  "season": "2021-2022",
  "teams": 20,
  "table": [
    {
      "team": "Man City",
      "played": 38,
      "wins": 29,
      "draws": 6,
      "losses": 3,
      "points": 93
    }
  ]
}
```

---

# 4 Expected Points Table (xPoints)

### Endpoint

```
GET /api/analytics/predict-table/
```

### Description

Generates a predicted league table based on expected results calculated using the Poisson probability model.

### Example

```
/api/analytics/predict-table/?season=2021-2022
```

### Example Response

```json
{
  "season": "2021-2022",
  "table": [
    {
      "team": "Liverpool",
      "xpoints": 89.4,
      "xgf": 92.1,
      "xga": 31.2
    }
  ]
}
```

---

# 5 Team Performance Summary

### Endpoint

```
GET /api/analytics/performance/
```

### Parameters

| Parameter | Description              |
| --------- | ------------------------ |
| season    | Season identifier        |
| team      | Team name                |
| last      | Number of recent matches |

### Example

```
/api/analytics/performance/?season=2021-2022&team=Arsenal&last=5
```

### Example Response

```json
{
  "team": "Arsenal",
  "overall": {
    "played": 38,
    "wins": 22,
    "draws": 3,
    "losses": 13,
    "points": 69
  },
  "form_last_n": {
    "n": 5,
    "sequence": ["W","W","L","L","W"]
  }
}
```

---

# 6 Win Probability Model

### Endpoint

```
GET /api/analytics/win-probability/
```

### Parameters

| Parameter | Description |
| --------- | ----------- |
| season    | Season      |
| home      | Home team   |
| away      | Away team   |

Example:

```
/api/analytics/win-probability/?season=2021-2022&home=Arsenal&away=Chelsea
```

### Example Response

```json
{
  "season": "2021-2022",
  "home": "Arsenal",
  "away": "Chelsea",
  "probabilities": {
    "home_win": 0.187,
    "draw": 0.274,
    "away_win": 0.538
  }
}
```

---

# 7 Batch Win Probability

### Endpoint

```
GET /api/analytics/win-probability/batch/
```

### Description

Computes match win probabilities against multiple opponents.

Example:

```
/api/analytics/win-probability/batch/?season=2021-2022&home=Arsenal
```

### Example Response

```json
{
  "team": "Arsenal",
  "matches": [
    {
      "opponent": "Chelsea",
      "home_win": 0.19,
      "draw": 0.27,
      "away_win": 0.54
    }
  ]
}
```

---

# Dashboard

The project also provides a web interface for interacting with the API.

```
/dashboard/
```

The dashboard allows users to:

* view league tables
* view expected points tables
* compute win probabilities
* perform CRUD operations on teams

---

# Error Handling

The API returns structured error responses.

Example:

```json
{
  "error": "Team not found"
}
```

Typical status codes:

| Code | Meaning            |
| ---- | ------------------ |
| 200  | Success            |
| 201  | Resource created   |
| 400  | Bad request        |
| 404  | Resource not found |
| 500  | Server error       |

---

# Technologies Used

* Django
* Python
* SQLite
* REST API design
* Poisson probability model
* JavaScript dashboard interface
