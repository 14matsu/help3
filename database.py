import os
from datetime import datetime
import pandas as pd
from supabase import create_client, Client
import streamlit as st
from constants import AREAS
from dotenv import load_dotenv

# ローカル環境の場合のみ.envファイルを読み込む
if not os.environ.get('STREAMLIT_CLOUD'):
    load_dotenv()

class SupabaseDB:
    def __init__(self):
        # Streamlitのシークレットまたは環境変数からSupabaseの認証情報を取得
        if st.secrets.get("env") == "prod":  # または明示的に環境を指定
            supabase_url = st.secrets.get("supabase_url")
            supabase_key = st.secrets.get("supabase_key")
        else:
            # ローカル環境用の設定（.envファイルから読み込み）
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            
            if not supabase_url or not supabase_key:
                raise Exception("環境変数 SUPABASE_URL と SUPABASE_KEY が設定されていません")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def init_db(self):
        try:
            # テーブルの存在確認
            self.supabase.table('shifts').select("*").limit(1).execute()
            self.supabase.table('store_help_requests').select("*").limit(1).execute()
            return True
        except Exception as e:
            st.error(f"データベース接続エラー: {e}")
            return False

    def get_shifts(self, start_date, end_date):
        try:
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Supabaseからデータを取得
            response = self.supabase.table('shifts')\
                .select("*")\
                .gte('date', start_date_str)\
                .lte('date', end_date_str)\
                .execute()
            
            if not response.data:
                return pd.DataFrame()
            
            # データフレームに変換
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date'])
            
            # ピボットテーブルを作成
            pivot_df = df.pivot(index='date', columns='employee', values='shift')
            return pivot_df
            
        except Exception as e:
            st.error(f"シフトデータの取得エラー: {e}")
            return pd.DataFrame()

    def save_shift(self, date, employee, shift_str):
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # データをUpsert（更新または挿入）
            self.supabase.table('shifts')\
                .upsert({
                    'date': date_str,
                    'employee': employee,
                    'shift': shift_str
                })\
                .execute()
            
            return True
        except Exception as e:
            st.error(f"シフトの保存エラー: {e}")
            return False

    def save_store_help_request(self, date, store, help_time):
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # データをUpsert
            self.supabase.table('store_help_requests')\
                .upsert({
                    'date': date_str,
                    'store': store,
                    'help_time': help_time
                })\
                .execute()
            
            return True
        except Exception as e:
            st.error(f"店舗ヘルプ希望の保存エラー: {e}")
            return False

    def get_store_help_requests(self, start_date, end_date):
        try:
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Supabaseからデータを取得
            response = self.supabase.table('store_help_requests')\
                .select("*")\
                .gte('date', start_date_str)\
                .lte('date', end_date_str)\
                .execute()
            
            if not response.data:
                return pd.DataFrame()
            
            # データフレームに変換
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date'])
            
            # ピボットテーブルを作成
            pivot_df = df.pivot(index='date', columns='store', values='help_time').fillna('-')
            
            # 全ての店舗列が存在することを確認
            all_stores = [store for stores in AREAS.values() for store in stores]
            for store in all_stores:
                if store not in pivot_df.columns:
                    pivot_df[store] = '-'
            
            return pivot_df
            
        except Exception as e:
            st.error(f"店舗ヘルプ希望の取得エラー: {e}")
            return pd.DataFrame()

# データベースのシングルトンインスタンスを作成
db = SupabaseDB()