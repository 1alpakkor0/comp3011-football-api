# Football Analytics API – COMP3011

## Overview

This project implements a **data-driven REST API for football analytics**, built using Django.
The system stores English Premier League match data and provides analytical endpoints to explore league standings, team performance, and match predictions.

The API supports **CRUD operations for teams**, advanced analytics, and a **dashboard interface** for interactive visualisation.

The project was developed as part of the **COMP3011 – Web Services and Web Data** module.

---

# Features

The system provides several football analytics capabilities:

### Core API Features

* RESTful API endpoints
* CRUD operations for football teams
* Structured JSON responses
* Proper HTTP status codes and error handling

### Analytics Endpoints

* **League Table**

  * Computes standings based on match results

* **Expected Points Table**

  * Predicts standings using probabilistic modelling

* **Team Performance Summary**

  * Displays match statistics, form, streaks, and goal differences

* **Win Probability Prediction**

  * Calculates match outcome probabilities using a **Poisson goals model**

* **Batch Probability Analysis**

  * Computes probabilities for multiple opponents

### Web Dashboard

A simple dashboard allows users to:

* view league tables
* view predicted tables
* compute match win probabilities
* perform CRUD operations for teams

Dashboard URL:

```
http://localhost:8000/dashboard/
```

---

# Technologies Used

* **Python**
* **Django**
* **SQLite**
* **JavaScript**
* **HTML / CSS**
* **REST API design**

The project also applies **statistical modelling using a Poisson distribution** to estimate football match outcomes.

---

# Dataset

The API uses publicly available **English Premier League datasets** containing match results and statistics.

Dataset contents include:

* match dates
* home and away teams
* goals scored
* season information

Example seasons included in this project:

* 2020–2021
* 2021–2022

Dataset source:

```
Kaggle – English Premier League Data
```

---


---

# Installation

## 1 Clone the repository

```
git clone https://github.com/YOUR_USERNAME/comp3011-football-api.git
cd comp3011-football-api/football_api_project
```

---

## 2 Install dependencies

```
pip install -r requirements.txt
```

If requirements.txt is not available, install:

```
pip install django
```

---

## 3 Apply database migrations

```
python manage.py migrate
```

---

## 4 Import match dataset

Example:

```
python manage.py import_epl ../data/2021-2022.csv 2021-2022
python manage.py import_epl ../data/2020-2021.csv 2020-2021
```

---

## 5 Run the server

```
python manage.py runserver
```

Server will start at:

```
http://localhost:8000
```

---

# Using the API

Example endpoints:

## League Table

```
GET /api/analytics/table/?season=2021-2022
```

---

## Expected Table

```
GET /api/analytics/predict-table/?season=2021-2022
```

---

## Team Performance

```
GET /api/analytics/performance/?season=2021-2022&team=Arsenal&last=5
```

---

## Win Probability

```
GET /api/analytics/win-probability/?season=2021-2022&home=Arsenal&away=Chelsea
```

---

## Teams CRUD

List teams

```
GET /api/teams/
```

Create team

```
POST /api/teams/
```

Update team

```
PUT /api/teams/{id}/
```

Delete team

```
DELETE /api/teams/{id}/
```

---

# Dashboard

A browser dashboard is available for interacting with the API.

```
http://localhost:8000/dashboard/
```

The dashboard allows users to:

* view league standings
* compute match probabilities
* explore analytics results
* manage teams using CRUD operations

---

# Win Probability Model

Match outcome probabilities are estimated using a **Poisson distribution model**.

Expected goals are calculated using:

```
λ_home = league_home_avg × home_attack_strength × away_defence_weakness
λ_away = league_away_avg × away_attack_strength × home_defence_weakness
```

These expected goals are then used to compute probabilities for:

* home win
* draw
* away win

using Poisson goal distributions.

---

# Limitations

* The model assumes goal scoring follows a Poisson distribution.
* Player transfers and injuries are not considered.
* Predictions rely solely on historical match statistics.

Future improvements could include:

* machine learning models
* player-level statistics
* advanced expected goals models (xG)

---

# Author

Alp Akkor
University of Leeds
BSc Computer Science

Module: **COMP3011 – Web Services and Web Data**

