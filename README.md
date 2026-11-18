# ZeroHunter Framework

منظومة فحص كود واكتشاف ثغرات (SAST + LibFuzzer/ASan) مدعومة بنموذجك الخاص بصيغة GGUF عبر GitHub Actions.

## الإعداد الآمن
1. أضف `HF_TOKEN` في إعدادات المستودع: **Settings → Secrets and variables → Actions**.
2. استخدم `GITHUB_TOKEN` التلقائي في GitHub Actions، وأضف `GITHUB_TOKEN` في **Streamlit Secrets** عند نشر `streamlit_app.py`.
3. درّب النموذج على Google Colab عبر `train.py` ثم ارفعه بـ `upload_hf.py` كملف `.gguf` مدمج.
