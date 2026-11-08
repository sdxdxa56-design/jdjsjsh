%%writefile upload_final.py
from huggingface_hub import HfApi, login

HF_TOKEN = "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"

print("1. جاري تسجيل الدخول...")
login(token=HF_TOKEN)

api = HfApi()
username = api.whoami()["name"]
repo_id = f"{username}/zerohunter-qwen-7b"

print(f"2. جاري إنشاء مستودع باسم: {repo_id}")
api.create_repo(repo_id=repo_id, exist_ok=True)

print("3. جاري رفع النموذج من Google Drive (قد يأخذ دقيقة)...")
api.upload_folder(
    folder_path="/content/drive/MyDrive/zerohunter_model",
    repo_id=repo_id,
    repo_type="model"
)
print("✅ 4. تم رفع النموذج بنجاح!")
print(f"🔗 رابط النموذج: https://huggingface.co/{repo_id}")
