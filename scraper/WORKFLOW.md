# LinkedIn Scraper Workflow

This directory contains a robust LinkedIn profile scraper designed to extract a user's full profile data into a structured JSON format.

## 🚀 Quick Start

1.  **Install Dependencies**
    ```bash
    npm install
    ```

2.  **Configure Credentials**
    Create a `.env` file in this directory with your LinkedIn login:
    ```ini
    LINKEDIN_EMAIL=your_email@example.com
    LINKEDIN_PASSWORD=your_password
    ```

3.  **Run Scraper**
    ```bash
    npm run scrape
    ```
    *This runs in "headless" mode (invisible browser).*

4.  **View Results**
    The data is saved to `profile_data.json`.

---

## 🛠️ Debugging

If you encounter issues (e.g., login challenges, CAPTCHA), you can run the scraper with the browser visible:

```bash
npm run scrape:debug
```

This allows you to manually intervene (e.g., solve a CAPTCHA) if necessary.

---

## 📦 Data Structure

The `profile_data.json` file contains:

| Section | Fields |
| :--- | :--- |
| **Identity** | `name`, `headline`, `location`, `about` (full text) |
| **Experience** | `company`, `title`, `employmentType`, `location`, `workType` (Remote/Hybrid), `startDate`, `endDate`, `duration`, `skills` (array), `companyLinkedInUrl` |
| **Education** | `school`, `degree`, `date` |
| **Skills** | Full list of skills |
| **Certifications** | `name`, `issuer`, `date`, `credentialUrl` |
| **Recommendations** | **Received Only**. Includes `author`, `authorTitle`, `authorLinkedInUrl`, and `text`. *Given* recommendations and *Pending requests* are automatically filtered out. |

---

## 🔄 Workflow for Updates

To update your profile data in the future:
1.  Ensure your LinkedIn profile is up to date on the website.
2.  Run `npm run scrape`.
3.  Use the generated `profile_data.json` in your portfolio or application.

## ⚠️ Notes
-   **Session Handling**: The scraper saves your session cookies to `session.json` to avoid repeated logins.
-   **Safety**: The scraper adds random delays and scrolls naturally to mimic human behavior.
