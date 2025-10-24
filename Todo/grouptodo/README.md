# 🎯 StrivePact: Group Goal & Accountability Platform

StrivePact is a Django app that helps users achieve goals through group accountability, task tracking, and virtual rewards. Complete tasks, review peers, earn points, and unlock badges to stay motivated and engaged.

---

## 🚀 Key Features

### 1. Group & Task Management
- **User & Profile**: Tracks Coins, Points, and Streaks for each user.  
- **Groups (Pacts)**: Users can create or join groups and manage members.  
- **Tasks**: Assign tasks to members; some require proof for completion.  

### 2. Financial Pool & Payout System
- **Coins (Virtual Wallet)**: Start with 100 Coins, can top-up.  
- **Weekly Pledge**: Commit Coins to the group’s weekly pool.  
- **Payout Logic**: Users completing all tasks earn back Coins plus a share of forfeited Coins.  

### 3. Proof of Work & Peer Review
- **Submission**: Submit proof for tasks marked `requires_proof`.  
- **Review**: Peers approve or request revision.  
- **Points**: Submitter earns 10 Points on approval, reviewer earns 3 Points.  

### 4. Gamification & Progress Tracking
- **Points & Leaderboard**: Track task completion and ranking.  
- **Streaks**: Tracks consecutive days of completing tasks.  
- **Badges**: Earn milestones like First Task, Reviewer, Streak Starter.  

---

## 📂 Models Overview
| Model | Purpose |
|-------|---------|
| User & Profile | Identity, Coins, Points, Streaks |
| Group (Pact) | Container for members & tasks |
| Task | Work unit, can require proof |
| WeeklyPledge | Tracks pledged Coins per week |
| TaskSubmission | Tracks submitted proof for review |

---

## ⚡ How It Works
1. Join or create a group (Pact).  
2. Add tasks and pledge Coins weekly.  
3. Submit tasks requiring proof; peers review.  
4. Complete tasks → earn Coins, points, streaks, and badges.  
5. Track progress on dashboard and leaderboard.  

---

