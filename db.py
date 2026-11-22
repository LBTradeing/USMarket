# === [SEC-01: IMPORTS & CONNECTION] ===
import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "")).strip()
    key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "")).strip()
    return create_client(url, key)


# === [SEC-02: FETCH MARKET SNAPSHOT & PROFILES] ===
@st.cache_data(ttl=300)
def load_market_data() -> pd.DataFrame:
    client = get_supabase_client()

    snap_resp = client.table("stocks_snapshot").select("*").execute()
    prof_resp = client.table("company_profiles").select("symbol, company_name, sector, industry, description").execute()

    snap_df = pd.DataFrame(snap_resp.data or [])
    prof_df = pd.DataFrame(prof_resp.data or [])

    if snap_df.empty:
        return pd.DataFrame()

    if not prof_df.empty:
        df = pd.merge(snap_df, prof_df, on="symbol", how="left")
    else:
        df = snap_df

    df = df.sort_values("symbol").reset_index(drop=True)
    return df
