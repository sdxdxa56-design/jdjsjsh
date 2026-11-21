# ZeroHunter Framework

منظومة فحص كود واكتشاف ثغرات (SAST + LibFuzzer/ASan) مدعومة بنموذجك الخاص بصيغة GGUF مع واجهة دردشة ورفع ملفات مضغوطة ومجلدات.

## 1. الإعداد الآمن
1. أضف `HF_TOKEN` في إعدادات المستودع: **Settings → Secrets and variables → Actions**.
2. استخدم `GITHUB_TOKEN` التلقائي في GitHub Actions، وأضف `GITHUB_TOKEN` في **Streamlit Secrets** عند نشر `streamlit_app.py`.
3. درّب النموذج على Google Colab عبر `notebooks/ZeroHunter_Train.ipynb` ثم ارفعه كملف `.gguf` مدمج.

## 2. التشغيل المحلي والدردشة مع فك الملفات المضغوطة (حتى بدون إنترنت)
- شغّل الواجهة مع نموذجك المحلي مباشرة:
  `ZEROHUNTER_LOCAL_MODEL=./zerohunter_gguf/zerohunter-7b-q5_k_m.gguf python3 web_app.py`
- ارفع ملف `.zip` أو مجلد من الواجهة، ثم اكتب **«فككه»** ليفك الأرشيف ويناقشك حول ملفاته ويفحصها.

## 3. التدريب التلقائي اليومي في الخلفية
- **تحديث بيانات الإنترنت في السحابة:** يعمل يومياً عبر `.github/workflows/auto-learn.yml`.
- **التدريب المحلي اليومي بالخلفية (يعمل حتى عند انقطاع الإنترنت):**
  `python3 auto_train_local.py --daemon`
