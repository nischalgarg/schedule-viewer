import streamlit as st
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from bs4 import BeautifulSoup
import pandas as pd
from collections import defaultdict
from datetime import datetime

# ---------------- SSL FIX (ONLY CHANGE) ---------------- #

class XLRIAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")  # allow weak DH
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

session = requests.Session()
session.mount("https://acad.xlri.ac.in", XLRIAdapter())

# ------------------------------------------------------ #

# Mapping: Roll Number → Name
roll_to_name = {
    "B24001": "Aarushi",
    "B24003": "Aditi",
    "B24010": "Ayush",
    "B24014": "Dhaarna",
    "B24017": "Dravya",
    "B24019": "Gautam",
    "B24032": "Nischal",
    "B24052": "Udit",
    "B24055": "Yamica",
    "B24183": "Harshita"
}
name_to_roll = {v: k for k, v in roll_to_name.items()}

# ✅ Cached fetch — refreshes every 8 hours
@st.cache_data(ttl=28800)
def fetch_schedule(sid):
    url = f"https://acad.xlri.ac.in/aisapp/ai/my-schedule.php?SID={sid}"
    response = session.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    schedule = []

    for card in soup.select('.card'):
        header = card.find('a')
        if not header:
            continue
        date_str = header.text.strip()

        table = card.find('table')
        if not table:
            continue
        tds = table.find_all('td')

        for i in range(0, len(tds), 3):
            subject = tds[i].text.strip()
            time = tds[i + 1].text.strip()
            venue = tds[i + 2].text.strip()
            schedule.append({
                'roll': sid,
                'date': date_str,
                'subject': subject,
                'time': time,
                'venue': venue
            })

    return schedule

# Streamlit UI
st.title("📘 XLRI Class Schedule Viewer")

all_names = list(name_to_roll.keys())

# Button to select all students
if st.button("Select All Students"):
    st.session_state.selected_names = all_names.copy()

# Initialize selection in session state
if "selected_names" not in st.session_state:
    st.session_state.selected_names = all_names.copy()

# Multiselect input
selected_names = st.multiselect(
    "Select students",
    options=all_names,
    default=st.session_state.selected_names,
    key="selected_names"
)

if st.button("Show Schedule"):
    if not selected_names:
        st.warning("Please select at least one student.")
    else:
        selected_rolls = [name_to_roll[name] for name in selected_names]
        combined = []

        for sid in selected_rolls:
            try:
                combined.extend(fetch_schedule(sid))
            except Exception as e:
                st.error(f"Error fetching schedule for {sid}: {e}")

        if combined:
            df = pd.DataFrame(combined)
            df['name'] = df['roll'].map(roll_to_name)

            grouped = defaultdict(list)
            for _, row in df.iterrows():
                key = (row['date'], row['subject'], row['time'], row['venue'])
                grouped[key].append(row['name'])

            rows = []
            for (date, subject, time, venue), names in grouped.items():
                rows.append({
                    'Date': date,
                    'Subject': subject,
                    'Time': time,
                    'Venue': venue,
                    'Students': ", ".join(sorted(set(names)))
                })

            df_grouped = pd.DataFrame(rows)

            def parse_date(date_str):
                try:
                    return datetime.strptime(
                        date_str.split('|')[-1].strip(), "%d-%m-%Y"
                    ).date()
                except:
                    return None

            def parse_time(time_str):
                try:
                    return datetime.strptime(time_str, "%I.%M %p").time()
                except:
                    return None

            df_grouped['parsed_date'] = df_grouped['Date'].apply(parse_date)
            df_grouped['parsed_time'] = df_grouped['Time'].apply(parse_time)

            today = datetime.today().date()
            df_upcoming = df_grouped[
                df_grouped['parsed_date'] >= today
            ].sort_values(by=['parsed_date', 'parsed_time', 'Subject'])

            if df_upcoming.empty:
                st.info("🎉 No upcoming classes found.")
            else:
                for parsed_date, group_df in df_upcoming.groupby("parsed_date"):
                    display_date = group_df["Date"].iloc[0]
                    st.subheader(f"📅 {display_date}")
                    st.dataframe(
                        group_df.drop(
                            columns=["Date", "parsed_date", "parsed_time"]
                        ).reset_index(drop=True)
                    )
        else:
            st.warning("No schedule data found.")
