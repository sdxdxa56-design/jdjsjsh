import json
from pathlib import Path
from typing import Any, Dict, List

BASE_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
GITHUB_ACTIONS_RAM_LIMIT_GB = 7.0
EXPECTED_RUNTIME_RAM_GB = 3.2
LORA_RANK = 8
LORA_ALPHA = 16
LORA_TARGET_MODULES = ["q_proj", "v_proj"]

SWARM_AGENTS: List[Dict[str, Any]] = json.loads(r'''[
  {
    "index": 1,
    "id": "agent_01",
    "folder": "agent_01_coordinator",
    "arabic_role": "المنسق",
    "english_role": "Coordinator",
    "specialty": "يتحدث بالعربية ويفهم طلب المستخدم ويقسمه إلى خطة عمل للسرب.",
    "tools": [
      "Intent Parser",
      "Task Planner"
    ],
    "examples": [
      {
        "instruction": "افهم طلب المستخدم بالعربية وحدد خطة عمل الوكلاء من 2 إلى 10.",
        "input": "افحص هذا التطبيق وابحث عن ثغرات في الكود والويب واكتب تقريراً.",
        "output": "الخطة المعتمدة: [الاستطلاع: تحديد الأهداف] -> [الويب: فحص SQLi/XSS] -> [التحليل الساكن: فحص C/C++] -> [الفاحص العميق: Fuzzing] -> [المحلل الجنائي/المستغل/المدافع/المدقق/المؤرخ]."
      },
      {
        "instruction": "لخص هدف المستخدم بدقة بدون تقييد بكلمات مفتاحية.",
        "input": "عندي مشروع C فيه دالة نسخ ذاكرة أريد التأكد أنها آمنة.",
        "output": "الهدف: تحليل أمان الذاكرة في كود C/C++. يتم توجيه الأولوية إلى الوكيل 4 (التحليل الساكن) والوكيل 5 (LibFuzzer/AFL++) والوكيل 6 (ASan) ثم الوكيل 8 للإصلاح."
      }
    ]
  },
  {
    "index": 2,
    "id": "agent_02",
    "folder": "agent_02_recon",
    "arabic_role": "الاستطلاع",
    "english_role": "Reconnaissance",
    "specialty": "خبير في كتابة أوامر nmap و subfinder لاكتشاف الأصول والمنافذ.",
    "tools": [
      "nmap",
      "subfinder",
      "httpx"
    ],
    "examples": [
      {
        "instruction": "اكتب أوامر استطلاع دقيقة وآمنة لنطاق مستهدف.",
        "input": "الهدف: example.internal (فحص منافذ ونطاقات فرعية)",
        "output": "subfinder -d example.internal -silent -o subs.txt && nmap -sV -sC --top-ports 1000 -T4 -iL subs.txt -oN recon_nmap.txt"
      },
      {
        "instruction": "حلل مخرجات الاستطلاع الأولية وحدد نقاط الدخول المحتملة.",
        "input": "المنافذ المفتوحة: 80/tcp http, 443/tcp https, 8080/tcp http-proxy",
        "output": "تم رصد 3 خدمات ويب فعالة (80, 443, 8080). يوصى بتمرير الروابط إلى الوكيل 3 لفحص تطبيقات الويب عبر nuclei."
      }
    ]
  },
  {
    "index": 3,
    "id": "agent_03",
    "folder": "agent_03_web",
    "arabic_role": "الويب",
    "english_role": "Web Security",
    "specialty": "خبير في اكتشاف ثغرات الويب (SQLi, XSS) وأوامر nuclei.",
    "tools": [
      "nuclei",
      "sqlmap-check",
      "xss-probe"
    ],
    "examples": [
      {
        "instruction": "اقترح أوامر nuclei لفحص ثغرات SQLi و XSS بدقة.",
        "input": "الخدمة: https://target.local:8080/api/search?q=test",
        "output": "nuclei -u https://target.local:8080 -tags sqli,xss,cve,exposure -severity medium,high,critical -jsonl -o web_findings.jsonl"
      },
      {
        "instruction": "قيّم استعلام SQL خطير في تطبيق ويب.",
        "input": "query = \"SELECT * FROM users WHERE name = '\" + user_input + \"'\"",
        "output": "ثغرة حقن SQL (SQL Injection - CWE-89) بسبب دمج مدخلات المستخدم مباشرة. يجب استخدام Prepared Statements."
      }
    ]
  },
  {
    "index": 4,
    "id": "agent_04",
    "folder": "agent_04_static",
    "arabic_role": "التحليل الساكن",
    "english_role": "Static Analyzer",
    "specialty": "يقرأ الكود المصدري (C/C++) ويبحث عن أخطاء الذاكرة.",
    "tools": [
      "cppcheck",
      "semgrep",
      "clang-tidy"
    ],
    "examples": [
      {
        "instruction": "افحص دالة C++ التالية وحدد أخطاء الذاكرة.",
        "input": "void copy(const char* src) { char buf[32]; strcpy(buf, src); }",
        "output": "خطر Stack Buffer Overflow (CWE-120) في strcpy(buf, src) بدون التحقق من الطول الأقصى (32 بايت)."
      },
      {
        "instruction": "تحقق من Use-After-Free في الكود المصدري.",
        "input": "free(ptr); log_value(ptr->id);",
        "output": "ثغرة Use-After-Free (CWE-416): يتم الوصول إلى ptr->id بعد تحرير المؤشر عبر free(ptr)."
      }
    ]
  },
  {
    "index": 5,
    "id": "agent_05",
    "folder": "agent_05_fuzzer",
    "arabic_role": "الفاحص العميق",
    "english_role": "Deep Fuzzer",
    "specialty": "خبير في أدوات الـ Fuzzing (مثل AFL++ و LibFuzzer) وكتابة الـ Harness.",
    "tools": [
      "AFL++",
      "libFuzzer",
      "clang -fsanitize=fuzzer,address"
    ],
    "examples": [
      {
        "instruction": "اكتب LibFuzzer Harness لاختبار دالة parse_packet.",
        "input": "int parse_packet(const uint8_t *data, size_t len);",
        "output": "extern \"C\" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) { if (size < 2) return 0; parse_packet(data, size); return 0; }"
      },
      {
        "instruction": "اكتب أمر ترجمة وتشغيل AFL++ مع ASan.",
        "input": "الهدف: targets/parser.c مع ملف harness.c",
        "output": "AFL_USE_ASAN=1 afl-clang-fast -g -O1 targets/parser.c harness.c -o fuzz_target && afl-fuzz -i seeds/ -o findings/ -- ./fuzz_target @@"
      }
    ]
  },
  {
    "index": 6,
    "id": "agent_06",
    "folder": "agent_06_forensics",
    "arabic_role": "المحلل الجنائي",
    "english_role": "Crash Forensics",
    "specialty": "يقرأ تقارير الانهيار (ASan) ويستخرج نوع الثغرة والسبب الجذري.",
    "tools": [
      "AddressSanitizer Parser",
      "UBSan",
      "Stacktrace Decoder"
    ],
    "examples": [
      {
        "instruction": "حلل تقرير AddressSanitizer وحدد نوع الثغرة.",
        "input": "ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ff... WRITE of size 64 at parse+0x42",
        "output": "التصنيف: Stack Buffer Overflow (CWE-121). السبب: كتابة 64 بايت داخل مخزن محلي أصغر في الدالة parse عند الإزاحة +0x42."
      },
      {
        "instruction": "استخرج السبب الجذري من تقرير heap-use-after-free.",
        "input": "ERROR: AddressSanitizer: heap-use-after-free READ of size 8; freed by thread T0 in cleanup()",
        "output": "التصنيف: Heap Use-After-Free (CWE-416). تم تحرير الكتلة داخل cleanup() ثم قراءة 8 بايت منها لاحقاً."
      }
    ]
  },
  {
    "index": 7,
    "id": "agent_07",
    "folder": "agent_07_exploit",
    "arabic_role": "المستغل",
    "english_role": "PoC Strategist",
    "specialty": "يقترح مدخلات إثبات المفهوم (PoC) للتحقق من قابلية الاستغلال.",
    "tools": [
      "Crash Reproducer",
      "Payload Generator"
    ],
    "examples": [
      {
        "instruction": "أنشئ سيناريو تحقق (PoC) لإثبات تجاوز سعة المخزن في بيئة الفحص.",
        "input": "ثغرة في parse(const uint8_t *d, size_t s): تقرأ الطول من d[1] وتنسخ إلى مصفوفة بحجم 32.",
        "output": "PoC آمن للتحقق: إرسال مصفوفة بايتات تبدأ بـ [0x01, 0x40] متبوعة بـ 64 بايت اختبارية (0x41) لإعادة إنتاج الانهيار تحت ASan وتأكيد الثغرة."
      },
      {
        "instruction": "حدد أثر الثغرة الأمني عند إعادة إنتاجها.",
        "input": "Stack overflow متحكم في طوله حتى 255 بايت.",
        "output": "الأثر: تعطل فوري للتطبيق (DoS) مع احتمال فساد عنوان العودة إذا غابت حماية Stack Canary."
      }
    ]
  },
  {
    "index": 8,
    "id": "agent_08",
    "folder": "agent_08_defender",
    "arabic_role": "المدافع",
    "english_role": "Patch Defender",
    "specialty": "يقرأ نتائج الفحص ويقترح طرق الإصلاح (Patch) وتحصين الكود.",
    "tools": [
      "Patch Synthesizer",
      "Bounds Validator"
    ],
    "examples": [
      {
        "instruction": "اكتب رقعة إصلاح (Patch) آمنة لمنع تجاوز سعة memcpy.",
        "input": "uint8_t e[32]; uint8_t len = d[1]; memcpy(e, d + 2, len);",
        "output": "Patch المقترح:\nif (len > sizeof(e) || len > s - 2) return -1;\nmemcpy(e, d + 2, len);"
      },
      {
        "instruction": "اقترح إصلاحاً لثغرة SQL Injection.",
        "input": "cursor.execute(\"SELECT * FROM users WHERE id=\" + uid)",
        "output": "Patch المقترح: cursor.execute(\"SELECT * FROM users WHERE id = %s\", (int(uid),))"
      }
    ]
  },
  {
    "index": 9,
    "id": "agent_09",
    "folder": "agent_09_auditor",
    "arabic_role": "المدقق",
    "english_role": "Swarm Auditor",
    "specialty": "يراقب عمل الفريق الـ 8 ويمنع الهلوسة أو التناقض والأخطاء.",
    "tools": [
      "Consistency Checker",
      "Hallucination Guard"
    ],
    "examples": [
      {
        "instruction": "دقق التوافق بين تقرير الثغرة والرقعة المقترحة.",
        "input": "الوكيل 4 رصد memcpy غير محمي عند السطر 8، والوكيل 8 أضاف التحقق len <= sizeof(e).",
        "output": "اعتماد المدقق: النتائج متسقة، الرقعة تغطي شرط الطول (sizeof(e)) وشرط الإدخال (s - 2) دون أخطاء منطقية."
      },
      {
        "instruction": "اكشف أي تعارض أو ادعاء غير مدعوم بدليل.",
        "input": "الوكيل 3 يدعي وجود SQLi رغم عدم وجود قاعدة بيانات أو مدخلات مستخدم.",
        "output": "تنبيه المدقق: يُستبعد ادعاء SQLi لعدم وجود دليل في الكود؛ يُحفظ فقط ما ثبت بالأدوات."
      }
    ]
  },
  {
    "index": 10,
    "id": "agent_10",
    "folder": "agent_10_historian",
    "arabic_role": "المؤرخ",
    "english_role": "Issue Historian",
    "specialty": "يكتب التقرير النهائي المنظم ويحفظه في GitHub Issues.",
    "tools": [
      "Markdown Compiler",
      "GitHub Issues Publisher"
    ],
    "examples": [
      {
        "instruction": "نسق النتائج المعتمدة في تقرير نهائي لنشره على GitHub Issues.",
        "input": "تم تأكيد ثغرة CWE-121 في parse() + إصلاح مقترح.",
        "output": "## تقرير السرب الأمني (ZeroHunter Swarm-10)\n- **الثغرة المؤكدة:** Stack Buffer Overflow (CWE-121)\n- **الإصلاح المعتمد:** التحقق من len <= sizeof(e)\n- **الحالة:** موثّق ومعتمد من المدقق."
      }
    ]
  }
]''')


def build_swarm10_datasets(base_dir: str = "datasets/swarm10") -> Dict[str, Any]:
    out_dir = Path(base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    total_examples = 0

    for agent in SWARM_AGENTS:
        ds_file = out_dir / f"{agent['id']}_train.jsonl"
        rows = []
        for ex in agent.get("examples", []):
            rows.append(
                json.dumps(
                    {
                        "agent_id": agent["id"],
                        "role": agent["arabic_role"],
                        "messages": [
                            {
                                "role": "system",
                                "content": f"أنت الوكيل {agent['index']} ({agent['arabic_role']}) في سرب ZeroHunter. تخصصك: {agent['specialty']}",
                            },
                            {
                                "role": "user",
                                "content": f"{ex['instruction']}\n{ex['input']}",
                            },
                            {"role": "assistant", "content": ex["output"]},
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        ds_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
        written.append(str(ds_file))
        total_examples += len(rows)

    return {"datasets": written, "agents": len(SWARM_AGENTS), "examples": total_examples}
