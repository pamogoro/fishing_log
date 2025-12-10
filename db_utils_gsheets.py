# db_utils_gsheets.py
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
from typing import Optional
import cloudinary
import cloudinary.uploader

@st.cache_resource(show_spinner=False)
def _init_cloudinary():
    cfg = st.secrets["cloudinary"]
    cloudinary.config(
        cloud_name = cfg["cloud_name"],
        api_key    = cfg["api_key"],
        api_secret = cfg["api_secret"],
        secure     = True,
    )
    return True


# 列定義（ヘッダ順を固定）
COLUMNS = ["id","date","time","area","tide_type","tide_height","temperature",
           "wind_direction","lure","action","size","image_url"]
SHEET_NAME = "logs"  # シート名は好きに

@st.cache_resource(show_spinner=False)
def _ws():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    sa = {k: st.secrets["gsheets"][k] for k in (
        "type","project_id","private_key_id","private_key","client_email","client_id",
        "auth_uri","token_uri","auth_provider_x509_cert_url","client_x509_cert_url"
    )}
    creds = Credentials.from_service_account_info(sa, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows="2000", cols=str(len(COLUMNS)))
        ws.append_row(COLUMNS)
    # ヘッダ確認
    if ws.row_values(1) != COLUMNS:
        ws.update("A1", [COLUMNS])
    return ws

def _to_df(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    for col in ["tide_height","temperature","size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def fetch_all() -> pd.DataFrame:
    ws = _ws()
    vals = ws.get_all_values()
    if len(vals) <= 1:
        return pd.DataFrame(columns=COLUMNS)
    return _to_df(vals[1:])

def _next_id(df: pd.DataFrame) -> int:
    if df.empty or df["id"].isna().all():
        return 1
    return int(df["id"].max()) + 1

# 既存のシグネチャに合わせる（fishing_log_app.py の呼び出しを変えない）
def insert_row(date: str, time: Optional[str], area: str, tide_type: str,
               tide_height: Optional[float], temperature: Optional[float],
               wind_direction: Optional[str], lure: Optional[str],
               action: Optional[str], size: Optional[float],
               image_url: Optional[str] = None,
               ) -> None:
    ws = _ws()
    df = fetch_all()
    new_id = _next_id(df)
    row = [
        str(new_id),
        date or "",
        (time or "00:00"),
        area or "",
        tide_type or "",
        "" if tide_height is None else str(tide_height),
        "" if temperature is None else str(temperature),
        wind_direction or "",
        lure or "",
        action or "",
        "" if size is None else str(size),
        image_url or "",
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")

def update_row(row_id: int, area: str, tide_type: str, temperature: Optional[float],
               wind_direction: Optional[str], lure: Optional[str], action: Optional[str],
               size: Optional[float], tide_height: Optional[float], time: Optional[str],
               image_url: Optional[str] = None) -> None:
    ws = _ws()
    ids = ws.col_values(1)
    try:
        r = ids.index(str(row_id)) + 1  # 1-indexed（ヘッダが1行目）
    except ValueError:
        return  # 見つからなければ何もしない（必要なら例外でもOK）

    # date は既存を保持（必要なら外から渡すように拡張してOK）
    existing_date = ws.cell(r, 2).value or ""
    existing_image_url = ws.cell(r, 12).value or ""

    values = [
        str(row_id),
        existing_date,
        (time or "00:00"),
        area or "",
        tide_type or "",
        "" if tide_height is None else str(tide_height),
        "" if temperature is None else str(temperature),
        wind_direction or "",
        lure or "",
        action or "",
        "" if size is None else str(size),
        image_url or existing_image_url,
    ]
    ws.update(f"A{r}:L{r}", [values], value_input_option="USER_ENTERED")

def delete_row(row_id: int) -> None:
    ws = _ws()
    ids = ws.col_values(1)
    try:
        r = ids.index(str(row_id)) + 1
    except ValueError:
        return
    if r == 1:  # ヘッダ保護
        return
    ws.delete_rows(r)

def upload_image_to_drive(file, filename: str) -> str:
    """
    Streamlit の file_uploader で受け取った file を
    Cloudinary にアップロードして、その公開URLを返す
    """
    _init_cloudinary()

    # public_id 用に拡張子抜いたり、フォルダ分けしたり
    import os
    name, ext = os.path.splitext(filename)
    public_id = f"fishing_log/{name}"

    # Streamlit の UploadedFile はそのまま file-like として渡せる
    result = cloudinary.uploader.upload(
        file,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
    )

    # HTTPS の URL
    return result["secure_url"]

def upload_image_to_cloudinary(file, filename: str) -> str:
    """
    Streamlit の file_uploader で受け取った file を
    Cloudinary にアップロードして、その公開URLを返す
    """
    _init_cloudinary()

    import os
    name, ext = os.path.splitext(filename)
    public_id = f"fishing_log/{name}"

    result = cloudinary.uploader.upload(
        file,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
    )

    return result["secure_url"]
