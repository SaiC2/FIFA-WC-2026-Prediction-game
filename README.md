# 🏆 Office World Cup Prediction League

A dynamic, interactive **Streamlit** dashboard designed to run and track an office prediction pool for the FIFA World Cup 2026. 

Unlike standard prediction brackets, this app utilizes a risk-reward "Pot" system: participants pick teams from different strength tiers (Pots A, B, C, D), and earn significantly more points when their underdog picks from weaker pots achieve success.

## ✨ Features
* **Zero-Config Data Integration**: The app automatically fetches the latest match schedules and live results from the open-source [OpenFootball JSON repository](https://github.com/openfootball/worldcup.json). No API keys or subscriptions required.
* **Intelligent Timezone Parsing**: All matches are natively converted to your local time (AEST) dynamically.
* **Interactive UI**: Includes an interactive group stage schedule with a calendar date-picker filter.
* **Title Race Tracker**: Features an interactive Plotly timeline graphing the exact moment participants jump ahead in the standings as the tournament progresses.
* **Automated Scoring**: Fully parses the complex OpenFootball nested JSON schemas to award points for wins, draws, penalty shootouts, and knockout stage advancements.

## ⚙️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repository-url>
   cd "fifa wc"
   ```

2. **Install the dependencies**:
   Ensure you have Python installed, then install the required packages:
   ```bash
   pip install streamlit pandas requests plotly pytz openpyxl
   ```

3. **Configure your participants**:
   The application requires a `users.xlsx` file in the root directory. This Excel file must contain the following columns:
   `Name`, `Pot A`, `Pot B`, `Pot C`, `Pot D`
   *(Add the participants' names and the country they selected from each pot).*

4. **Run the application**:
   ```bash
   streamlit run app.py
   ```

## 📜 Game Rules

The scoring system actively rewards participants who pick underdogs that perform well.

* **Pot A**: Tournament Favorites (Lowest risk, lowest reward)
* **Pot B/C**: Mid-tier competitors
* **Pot D**: Heavy Underdogs (Highest risk, highest reward)

Participants earn points for:
* Group Stage Wins and Draws
* Qualifying for the Round of 32, Round of 16, Quarter-Finals, Semi-Finals, and Finals
* Winning the World Cup Trophy

*(See the **Game Rules** tab inside the app for the full breakdown of points per Pot).*

## 🧪 Testing

The repository includes a dedicated test suite to verify the custom scoring engine calculation rules.
To run the automated tests natively:
```bash
python test_scoring.py
```
