# Telegram Bot Documentation

## Overview

This document is a simple guide for a Telegram bot that allows users to register, make requests, check their status, and see statistics. Administrators have extra features, like exporting requests to Excel and managing user submissions.

## Table of Contents

1. [Setup](#setup)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Bot Functionalities](#bot-functionalities)
   - [User Registration](#user-registration)
   - [Main Menu](#main-menu)
   - [Making a Request](#making-a-request)
   - [Checking Request Status](#checking-request-status)
   - [Active Requests Reminder](#active-requests-reminder)
   - [Exporting Requests](#exporting-requests)
   - [Request Approval/Rejection](#request-approvalrejection)
   - [Viewing Statistics](#viewing-statistics)
5. [Administrator Capabilities](#administrator-capabilities)
6. [Database Structure](#database-structure)
7. [Logging](#logging)
8. [Scheduler](#scheduler)

## Setup

### Installation

To set up the bot:

1. Clone the repository to your computer. git clone https://github.com/Kultup/FinanceRequestBot.git
2. Go to the project directory.
3. Install all necessary packages:

   ```bash
   pip install -r requirements.txt
   ```
