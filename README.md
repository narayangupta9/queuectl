# QueueCTL - Concurrency-Locked Background Job Queue

A production-grade, CLI-based background job queue system built with Python and SQLite. This system supports parallel worker execution, safe process-level concurrency control, automatic exponential backoff retries, and a Dead Letter Queue (DLQ) for permanently failed tasks.

## 🎥 Working CLI Demo
👉 [Click Here to Watch the Live Demo Video]https://drive.google.com/file/d/1CAlvDeNSdC0gPf_ZIYVM-xKjB8SSVr8_/view
*(Note: Video demonstrates enqueuing, worker processing loop, backoff, and DLQ tracking)*

---

## 🛠️ Setup Instructions
Follow these steps to set up and run the system locally:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/narayangupta9/queuectl.git](https://github.com/narayangupta9/queuectl.git)
   cd queuectl
