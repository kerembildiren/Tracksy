# Turkish-Super-League-toolkit

A lightweight **FastAPI** project and **Dataset Exporter** that provides comprehensive Turkish Super League data (standings, matches, player stats, and more) using `sofascore-wrapper`.


## Features

- **REST API:** Real-time endpoints for live scores, standings, fixtures, team profiles, and player attributes.
- **Dataset Exporter:** An interactive CLI tool to generate relational CSV datasets (goals, cards, lineups, etc.) for data science and Kaggle projects.
- **High Performance:** Built entirely with asynchronous Python (`asyncio`) for fast data retrieval.

## Tech Stack

**Language:** Python  
**Framework:** FastAPI, Uvicorn  
**Data Source:** sofascore-wrapper  

## Run Locally

Clone the project and go to project directory

```bash
git clone https://github.com/kaany43/Turkish-Super-League-toolkit.git
cd Turkish-Super-League-toolkit
```
Install dependencies
```bash
pip install -r requirements.txt
```
Start the API server
```bash
uvicorn main:app --loop asyncio --reload
```
## Full Documentation
Full documentation, including advanced usage and data structures, can be found [here](https://kaany43.github.io/Turkish-Super-League-toolkit/)

##

 Inspired by siriiuss/TFF-api

