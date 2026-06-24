import React, { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Mail,
  MessageCircle,
  Send,
} from "lucide-react";
import fullLogo from "./full-logo.jpg";
import "./TazaLanding.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "https://taza-bot-ssjy.onrender.com"
).replace(/\/$/, "");
const VENDOR_WHATSAPP = (import.meta.env.VITE_VENDOR_WHATSAPP || "").replace(
  /\D/g,
  ""
);
const TELEGRAM_URL = import.meta.env.VITE_TELEGRAM_URL || "";
const CONTACT_EMAIL = import.meta.env.VITE_CONTACT_EMAIL || "";

const categories = [
  { icon: "🥐", title: "المخابز والمعجنات" },
  { icon: "🍔", title: "المطاعم والوجبات" },
  { icon: "🍎", title: "الخضار والفواكه" },
  { icon: "🥫", title: "البقالة والتموين" },
  { icon: "🧁", title: "الحلويات" },
  { icon: "☕", title: "القهوة والمشروبات" },
];

const vendorCategories = [
  "مطعم ووجبات",
  "مخبز ومخبوزات",
  "وجبات سريعة",
  "خضار وفواكه",
  "بقالة وتموين",
  "حلويات ومعجنات",
  "قهوة ومشروبات",
];

const areas = [
  "دمشق – المزة",
  "دمشق – المالكي",
  "دمشق – باب توما",
  "دمشق – الميدان",
  "دمشق – ركن الدين",
  "حلب – الشهباء الجديدة",
  "حلب – العزيزية",
  "حلب – الجميلية",
  "حمص – الوعر",
  "حمص – عكرمة",
  "اللاذقية – الزراعة",
  "طرطوس المدينة",
];

const steps = [
  {
    num: "01",
    title: "أنشئ كيس اليوم",
    body: "حدد النوع والكمية والسعر ونافذة الاستلام. محتوى الكيس يبقى مرناً حسب الفائض الطازج المتوفر لديك.",
    icon: "✍️",
  },
  {
    num: "02",
    title: "يصل الحجز من زبون قريب",
    body: "يتصفح الزبائن الأكياس المتاحة ويحجزون قبل نفاد الكمية، ثم يحصلون على رمز استلام واضح.",
    icon: "🛍️",
  },
  {
    num: "03",
    title: "الاستلام من متجرك",
    body: "يحضر الزبون ضمن الوقت المحدد، يدفع عند الاستلام، ويتحقق فريقك من الرمز خلال ثوانٍ.",
    icon: "✅",
  },
];

const benefits = [
  {
    title: "حافظ على صورة علامتك",
    body: "اعرض أكياس مفاجآت بدلاً من تخفيض كل صنف علناً. تبقى قائمتك الأساسية وأسعارها كما هي.",
    icon: "🛡️",
  },
  {
    title: "أنت صاحب القرار",
    body: "تختار المحتوى والكمية والسعر ووقت الاستلام، وتستطيع تعديل العرض أو إيقافه في أي وقت.",
    icon: "🎛️",
  },
  {
    title: "تشغيل خفيف",
    body: "لا توصيل ولا أجهزة إضافية ولا تغيير في عمل المطبخ. حضّر الكيس قرب الإغلاق وسلمه من متجرك.",
    icon: "⚡",
  },
  {
    title: "زبائن جدد محليون",
    body: "فائض اليوم يصبح فرصة لاكتشاف متجرك والعودة إليه لاحقاً لشراء المنتجات بالسعر المعتاد.",
    icon: "📍",
  },
];

const screens = [
  {
    tag: "تصفح",
    title: "أكياس قريبة ومتاحة",
    body: "يرى الزبون المتجر والنوع والسعر ووقت الاستلام والكمية المتبقية.",
  },
  {
    tag: "حجز",
    title: "تفاصيل واضحة قبل الحجز",
    body: "يعرف الزبون قيمة الكيس ومكان الاستلام، ثم يؤكد الحجز دون دفع إلكتروني.",
  },
  {
    tag: "استلام",
    title: "رمز استلام آمن",
    body: "يعرض الزبون رمز TAZA، ويتحقق المطعم منه قبل تغيير حالة الطلب.",
  },
  {
    tag: "مطعم",
    title: "إنشاء كيس خلال دقائق",
    body: "خطوات قصيرة من تيليغرام لتحديد السعر والكمية والوقت ثم مراجعة العرض قبل نشره.",
  },
  {
    tag: "مطعم",
    title: "إدارة طلبات اليوم",
    body: "تابع المحجوز والمستلم والملغي، وتحقق من كل عملية استلام بالرمز.",
  },
  {
    tag: "مطعم",
    title: "صورة يومية بسيطة",
    body: "راقب الكمية المباعة والمتبقية والإيراد المتوقع من لوحة المطعم.",
  },
];

const faqs = [
  {
    q: "هل تجعل تازا متجري يبدو رخيصاً؟",
    a: "لا. تعرض تازا كيس مفاجآت محدوداً في نهاية اليوم، وليس قائمة تخفيضات علنية على منتجاتك الأساسية.",
  },
  {
    q: "هل أحتاج إلى خدمة توصيل؟",
    a: "أبداً. تازا تعتمد على الاستلام من المتجر ضمن الوقت الذي تحدده أنت.",
  },
  {
    q: "من يحدد محتوى الكيس؟",
    a: "أنت. ضع الفائض الطازج المتوفر فعلاً في ذلك اليوم، مع توضيح نوع الكيس دون الالتزام بأصناف ثابتة.",
  },
  {
    q: "ماذا لو لم يُحجز الكيس؟",
    a: "أنت تعرض فقط ما تريد وبالكمية التي تناسبك. لا توجد رسوم توصيل أو مخزون تنقله إلى تازا.",
  },
  {
    q: "هل يؤثر ذلك على المبيعات بالسعر الكامل؟",
    a: "الأكياس محدودة وقريبة من وقت الإغلاق، لذلك لا تحل محل المشتريات المعتادة خلال اليوم.",
  },
  {
    q: "كيف يتم الدفع؟",
    a: "يدفع الزبون للمطعم مباشرة عند الاستلام. لا توجد دفعة إلكترونية داخل تازا في مرحلة التجربة الحالية.",
  },
];

function useFadeIn() {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.unobserve(element);
        }
      },
      { threshold: 0.12 }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, className: `fade-in${visible ? " visible" : ""}` };
}

function FadeIn({ as = "div", className = "", children, ...rest }: any) {
  const { ref, className: fadeClass } = useFadeIn();
  const Tag = as as any;
  return (
    <Tag ref={ref} className={`${fadeClass} ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}

function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`header${scrolled ? " scrolled" : ""}`} id="top">
      <div className="wrap header-inner">
        <a href="#top" aria-label="العودة إلى بداية صفحة تازا">
          <img className="logo-img" src={fullLogo} alt="شعار تازا" />
        </a>
        <nav className="nav" aria-label="التنقل الرئيسي">
          <a href="#how">كيف تعمل</a>
          <a href="#vendors">للمتاجر</a>
          <a href="#app">تجربة التطبيق</a>
          <a href="#faq">الأسئلة</a>
        </nav>
        <div className="header-cta">
          <a className="btn btn-dark" href="#join">
            انضم كتاجر
          </a>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="hero" id="hero">
      <div className="wrap hero-inner">
        <div className="hero-copy">
          <span className="kicker">سوق محلي لإنقاذ فائض الطعام</span>
          <h1 className="hero-title">
            حوّل فائض اليوم إلى
            <br />
            <em>إيراد إضافي.</em>
          </h1>
          <p className="hero-sub">
            تساعد تازا المطاعم والمخابز والمقاهي على عرض فائضها الطازج في
            أكياس مفاجآت محدودة. يحجز الزبون ويستلم من متجرك قرب الإغلاق.
          </p>
          <div className="hero-actions">
            <a className="btn btn-white" href="#join">
              انضم إلى التجربة
              <ArrowLeft aria-hidden="true" />
            </a>
            <a className="btn btn-outline" href="#how">
              شاهد كيف تعمل
            </a>
          </div>
          <div className="trust-row">
            <span className="trust-chip">بدون توصيل</span>
            <span className="trust-chip">الدفع عند الاستلام</span>
            <span className="trust-chip">أنت تتحكم بالكيس</span>
            <span className="trust-chip">تشغيل عبر تيليغرام</span>
          </div>
        </div>

        <div className="hero-phone-wrap" aria-label="مثال على كيس في تطبيق تازا">
          <div className="phone-frame">
            <div className="phone-notch" />
            <div className="phone-app-bar">
              <span className="phone-brand">تازا</span>
              <span className="phone-pill">6 أكياس قريبة</span>
            </div>
            <div className="phone-card">
              <div className="phone-card-label">كيس مفاجآت من مخبز</div>
              <div className="phone-card-title">تشكيلة مخبوزات المساء</div>
              <div className="phone-card-time">الاستلام اليوم، 20:30 – 21:15</div>
              <div className="phone-price-row">
                <span className="phone-orig">قيمة 75,000 ل.س</span>
                <span className="phone-price">25,000 ل.س</span>
              </div>
            </div>
            <div className="phone-row">
              <span>الكمية المتبقية</span>
              <strong>3 أكياس</strong>
            </div>
            <div className="phone-row">
              <span>رمز الاستلام</span>
              <strong>TAZA-00042</strong>
            </div>
            <div className="phone-qr">
              {Array.from({ length: 20 }, (_, index) => (
                <span key={index} />
              ))}
            </div>
          </div>
          <div className="phone-badge">
            <strong>لا تجهيزات إضافية.</strong>
            الزبون يأتي إلى متجرك.
          </div>
        </div>
      </div>
    </section>
  );
}

function Marquee() {
  const items = [
    "حوّل الفائض إلى إيراد",
    "بدون أسطول توصيل",
    "استلام من المتجر",
    "أنت تتحكم بالكيس",
    "أنقذ الطعام وحسّن مزاجك",
    "مخابز · مقاهٍ · مطاعم",
  ];
  return (
    <div className="marquee-wrap" aria-hidden="true">
      <div className="marquee-track">
        {[...items, ...items].map((text, index) => (
          <span key={`${text}-${index}`}>
            {text} <span className="marquee-dot">✦</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Intro() {
  return (
    <section className="intro">
      <div className="wrap">
        <FadeIn as="span" className="kicker">
          نموذج بسيط وواضح
        </FadeIn>
        <FadeIn as="h2" className="section-title">
          فائض طازج يتحول إلى
          <br />
          كيس مفاجآت.
        </FadeIn>
        <FadeIn as="p" className="section-body intro-body">
          يعرف الزبون المتجر والنوع والقيمة والسعر ووقت الاستلام، بينما يبقى
          المحتوى مرناً لتبيع ما توفر لديك فعلاً دون تخفيض قائمتك صنفاً بصنف.
        </FadeIn>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="how" id="how">
      <div className="wrap">
        <FadeIn className="how-header">
          <span className="kicker">كيف تعمل تازا</span>
          <h2 className="section-title how-title">
            ثلاث خطوات تناسب واقع نهاية اليوم.
          </h2>
        </FadeIn>
        <div className="steps-grid">
          {steps.map((step) => (
            <FadeIn as="div" className="step-card" key={step.num}>
              <div className="step-num">{step.num}</div>
              <div className="step-icon" aria-hidden="true">
                {step.icon}
              </div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function Categories() {
  return (
    <section className="categories" id="categories">
      <div className="wrap">
        <FadeIn className="cat-header">
          <span className="kicker">أنشطة مناسبة لتازا</span>
          <h2 className="section-title">مصممة لمتاجر الطعام المحلية.</h2>
        </FadeIn>
        <div className="cat-grid">
          {categories.map((category) => (
            <FadeIn as="div" className="cat-card" key={category.title}>
              <div className="cat-icon">{category.icon}</div>
              <h3>{category.title}</h3>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function Benefits() {
  return (
    <section className="benefits" id="vendors">
      <div className="wrap benefits-inner">
        <FadeIn className="benefits-copy">
          <span className="kicker kicker-white">للمطاعم والمتاجر</span>
          <h2 className="section-title section-title--white">
            الإيراد أولاً.
            <br />
            وتقليل الهدر مكسب إضافي.
          </h2>
          <p className="section-body section-body--white">
            صُممت تازا لتستعيد قيمة طعام أعددته بالفعل، دون توصيل أو تعقيد
            تشغيلي، وبسيطرة كاملة من فريقك.
          </p>
          <div className="benefits-cta">
            <a className="btn btn-white" href="#join">
              سجّل متجرك
              <ArrowLeft aria-hidden="true" />
            </a>
          </div>
        </FadeIn>
        <div className="benefits-grid">
          {benefits.map((benefit) => (
            <FadeIn as="div" className="benefit-card" key={benefit.title}>
              <div className="benefit-icon">{benefit.icon}</div>
              <h3>{benefit.title}</h3>
              <p>{benefit.body}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function Calculator() {
  const [baskets, setBaskets] = useState(5);
  const [price, setPrice] = useState(25000);
  const [days, setDays] = useState(26);
  const total = baskets * price * days;
  const formatted = `${new Intl.NumberFormat("ar-SY").format(total || 0)} ل.س`;

  return (
    <section className="calculator" id="calculator">
      <div className="wrap calc-inner">
        <FadeIn>
          <span className="kicker">تقدير سريع للإيراد</span>
          <h2 className="section-title">كم يمكن أن يستعيد فائضك؟</h2>
          <p className="section-body">
            غيّر الأرقام بما يناسب متجرك لتأخذ فكرة أولية عن قيمة الطعام الذي
            يمكن بيعه بدلاً من بقائه دون استفادة.
          </p>
          <div className="calc-example">
            <p className="calc-example-label">
              مثال: 5 أكياس بسعر 25,000 ل.س خلال 26 يوماً
            </p>
            <p className="calc-example-value">3,250,000 ل.س شهرياً</p>
            <p className="calc-example-note">من طعام كان سيبقى دون بيع.</p>
          </div>
        </FadeIn>

        <FadeIn as="div" className="calc-panel">
          <div className="calc-field">
            <label htmlFor="baskets">عدد الأكياس يومياً</label>
            <input
              id="baskets"
              type="number"
              min={1}
              max={50}
              value={baskets}
              onChange={(event) => setBaskets(Number(event.target.value) || 0)}
            />
          </div>
          <div className="calc-field">
            <label htmlFor="price">متوسط سعر الكيس (ل.س)</label>
            <input
              id="price"
              type="number"
              min={1000}
              step={1000}
              max={1000000}
              value={price}
              onChange={(event) => setPrice(Number(event.target.value) || 0)}
            />
          </div>
          <div className="calc-field">
            <label htmlFor="days">أيام العمل شهرياً</label>
            <input
              id="days"
              type="number"
              min={1}
              max={31}
              value={days}
              onChange={(event) => setDays(Number(event.target.value) || 0)}
            />
          </div>
          <div className="calc-result-box">
            <span className="calc-result-label">الإيراد الشهري المستعاد</span>
            <span className="calc-result-value">{formatted}</span>
            <span className="calc-note">
              تقدير أولي قبل عمولة تازا، دون تكلفة توصيل أو موظفين إضافيين.
            </span>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

function AppPreview() {
  return (
    <section className="app-preview" id="app">
      <div className="wrap">
        <FadeIn>
          <span className="kicker">التجربة اليومية</span>
          <h2 className="section-title">
            حجز واضح يجعل عنصر المفاجأة مريحاً.
          </h2>
        </FadeIn>
        <div className="screens-grid">
          {screens.map((screen) => (
            <FadeIn as="div" className="screen-card" key={screen.title}>
              <span className="screen-tag">{screen.tag}</span>
              <h3>{screen.title}</h3>
              <p>{screen.body}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function FAQ() {
  return (
    <section className="faq" id="faq">
      <div className="wrap">
        <FadeIn>
          <span className="kicker">أسئلة شائعة</span>
          <h2 className="section-title">إجابات مباشرة على مخاوف التاجر.</h2>
        </FadeIn>
        <div className="faq-grid">
          {faqs.map((faq) => (
            <FadeIn as="details" className="faq-item" key={faq.q}>
              <summary>{faq.q}</summary>
              <p>{faq.a}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

type VendorForm = {
  shop_name: string;
  category: string;
  area: string;
  pickup_address: string;
  contact_name: string;
  whatsapp: string;
  closing_time: string;
  surplus_notes: string;
  company_website: string;
};

type SubmitResult = {
  lead_id: number;
  telegram_url: string;
};

const emptyForm: VendorForm = {
  shop_name: "",
  category: "",
  area: "",
  pickup_address: "",
  contact_name: "",
  whatsapp: "",
  closing_time: "",
  surplus_notes: "",
  company_website: "",
};

function VendorSignup() {
  const [form, setForm] = useState<VendorForm>(emptyForm);
  const [state, setState] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<SubmitResult | null>(null);
  const statusRef = useRef<HTMLDivElement | null>(null);

  function update<K extends keyof VendorForm>(key: K, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (state === "submitting") return;

    setState("submitting");
    setMessage("");
    setResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/vendor_lead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        throw new Error(data.message || "تعذر إرسال الطلب. حاول مجدداً.");
      }
      setResult({
        lead_id: Number(data.lead_id || 0),
        telegram_url: String(data.telegram_url || ""),
      });
      setState("success");
      setMessage(
        "تم حفظ طلبك. أكمل الخطوة الأخيرة في تيليغرام لربط الطلب بحسابك."
      );
      setForm(emptyForm);
    } catch (error) {
      setState("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "تعذر إرسال الطلب. حاول مجدداً."
      );
    } finally {
      requestAnimationFrame(() => {
        statusRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      });
    }
  }

  const hasDirectContacts =
    Boolean(VENDOR_WHATSAPP) || Boolean(TELEGRAM_URL) || Boolean(CONTACT_EMAIL);

  return (
    <section className="signup" id="join">
      <div className="wrap signup-inner">
        <FadeIn className="signup-copy">
          <span className="kicker kicker-white">تجربة التجار المؤسسين</span>
          <h2 className="section-title section-title--white">
            هل تريد تازا في متجرك؟
          </h2>
          <p className="section-body section-body--white">
            أرسل معلومات المتجر، ثم اربط الطلب بحسابك في تيليغرام. بعد
            المراجعة ستصلك رسالة التفعيل ولوحة العمل مباشرة داخل البوت.
          </p>
          {hasDirectContacts ? (
            <div className="contact-links">
              {VENDOR_WHATSAPP ? (
                <a
                  className="contact-link"
                  href={`https://wa.me/${VENDOR_WHATSAPP}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <MessageCircle size={18} aria-hidden="true" />
                  واتساب
                </a>
              ) : null}
              {TELEGRAM_URL ? (
                <a
                  className="contact-link"
                  href={TELEGRAM_URL}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Send size={18} aria-hidden="true" />
                  تيليغرام
                </a>
              ) : null}
              {CONTACT_EMAIL ? (
                <a className="contact-link" href={`mailto:${CONTACT_EMAIL}`}>
                  <Mail size={18} aria-hidden="true" />
                  البريد
                </a>
              ) : null}
            </div>
          ) : null}
        </FadeIn>

        <FadeIn as="div" className="form-box">
          <div className="form-title">عرّفنا بمتجرك</div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="f-shop">اسم المتجر</label>
                <input
                  id="f-shop"
                  type="text"
                  placeholder="مثال: مخبز الياسمين"
                  autoComplete="organization"
                  required
                  maxLength={100}
                  value={form.shop_name}
                  onChange={(event) => update("shop_name", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-category">نوع النشاط</label>
                <select
                  id="f-category"
                  required
                  value={form.category}
                  onChange={(event) => update("category", event.target.value)}
                >
                  <option value="">اختر نوع النشاط</option>
                  {vendorCategories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="f-area">المنطقة</label>
                <select
                  id="f-area"
                  required
                  value={form.area}
                  onChange={(event) => update("area", event.target.value)}
                >
                  <option value="">اختر المنطقة</option>
                  {areas.map((area) => (
                    <option key={area} value={area}>
                      {area}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="f-contact">اسم المسؤول</label>
                <input
                  id="f-contact"
                  type="text"
                  placeholder="الاسم الذي سيتواصل معه فريق تازا"
                  autoComplete="name"
                  required
                  maxLength={100}
                  value={form.contact_name}
                  onChange={(event) => update("contact_name", event.target.value)}
                />
              </div>
              <div className="field span-2">
                <label htmlFor="f-address">عنوان الاستلام بالتفصيل</label>
                <input
                  id="f-address"
                  type="text"
                  placeholder="مثال: المزة، قرب جامع الأكرم، بجانب..."
                  autoComplete="street-address"
                  required
                  maxLength={240}
                  value={form.pickup_address}
                  onChange={(event) =>
                    update("pickup_address", event.target.value)
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="f-whatsapp">رقم واتساب</label>
                <input
                  id="f-whatsapp"
                  type="tel"
                  dir="ltr"
                  placeholder="0933123456"
                  autoComplete="tel"
                  required
                  maxLength={30}
                  value={form.whatsapp}
                  onChange={(event) => update("whatsapp", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-closing">وقت الإغلاق المعتاد</label>
                <input
                  id="f-closing"
                  type="time"
                  required
                  value={form.closing_time}
                  onChange={(event) =>
                    update("closing_time", event.target.value)
                  }
                />
              </div>
              <div className="field span-2">
                <label htmlFor="f-surplus">الفائض المعتاد، إن وجد</label>
                <input
                  id="f-surplus"
                  type="text"
                  placeholder="مثال: معجنات، خبز، وجبات، حلويات"
                  maxLength={500}
                  value={form.surplus_notes}
                  onChange={(event) =>
                    update("surplus_notes", event.target.value)
                  }
                />
              </div>
              <div className="field honeypot" aria-hidden="true">
                <label htmlFor="company-website">موقع الشركة</label>
                <input
                  id="company-website"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={form.company_website}
                  onChange={(event) =>
                    update("company_website", event.target.value)
                  }
                />
              </div>
            </div>
            <button
              className="btn btn-dark form-submit"
              type="submit"
              disabled={state === "submitting"}
            >
              {state === "submitting" ? "جارٍ إرسال الطلب..." : "إرسال طلب الانضمام"}
              <ArrowLeft aria-hidden="true" />
            </button>
            <p className="form-note">
              لن يتم تفعيل المتجر قبل ربط الطلب بحساب تيليغرام ومراجعته من
              فريق تازا.
            </p>
          </form>

          {message ? (
            <div
              className={`form-status form-status--${state}`}
              ref={statusRef}
              role={state === "error" ? "alert" : "status"}
              aria-live="polite"
            >
              {state === "success" ? (
                <CheckCircle2 aria-hidden="true" />
              ) : null}
              <div>
                <h4>
                  {state === "success"
                    ? "تم استلام الطلب"
                    : "تعذر إرسال الطلب"}
                </h4>
                <p>{message}</p>
                {state === "success" && result?.telegram_url ? (
                  <a
                    className="btn btn-dark telegram-continue"
                    href={result.telegram_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    المتابعة في تيليغرام
                    <Send size={18} aria-hidden="true" />
                  </a>
                ) : null}
                {state === "error" ? (
                  <button
                    className="retry-button"
                    type="button"
                    onClick={() => setState("idle")}
                  >
                    عدّل البيانات وحاول مجدداً
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </FadeIn>
      </div>
    </section>
  );
}

function Footer() {
  const hasContacts =
    Boolean(VENDOR_WHATSAPP) || Boolean(TELEGRAM_URL) || Boolean(CONTACT_EMAIL);
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer-inner">
          <div className="footer-brand">
            <img className="footer-logo" src={fullLogo} alt="شعار تازا" />
            <p className="footer-tagline">
              أكياس مفاجآت محلية تساعد المتاجر على بيع فائضها الطازج وتمنح
              الزبائن قيمة أفضل.
            </p>
          </div>
          <div className="footer-col">
            <h4>تازا</h4>
            <ul>
              <li>
                <a href="#how">كيف تعمل</a>
              </li>
              <li>
                <a href="#categories">الأنشطة</a>
              </li>
              <li>
                <a href="#app">تجربة التطبيق</a>
              </li>
              <li>
                <a href="#calculator">حاسبة الإيراد</a>
              </li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>للتجار</h4>
            <ul>
              <li>
                <a href="#vendors">لماذا تازا؟</a>
              </li>
              <li>
                <a href="#faq">الأسئلة الشائعة</a>
              </li>
              <li>
                <a href="#join">سجّل متجرك</a>
              </li>
            </ul>
          </div>
          {hasContacts ? (
            <div className="footer-col">
              <h4>تواصل</h4>
              <ul>
                {VENDOR_WHATSAPP ? (
                  <li>
                    <a
                      href={`https://wa.me/${VENDOR_WHATSAPP}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      واتساب
                    </a>
                  </li>
                ) : null}
                {TELEGRAM_URL ? (
                  <li>
                    <a href={TELEGRAM_URL} target="_blank" rel="noreferrer">
                      تيليغرام
                    </a>
                  </li>
                ) : null}
                {CONTACT_EMAIL ? (
                  <li>
                    <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>
        <div className="footer-bottom">
          <span>© 2026 تازا. جميع الحقوق محفوظة.</span>
          <span>أنقذ الطعام وحسّن مزاجك.</span>
        </div>
      </div>
    </footer>
  );
}

export default function TazaLanding() {
  return (
    <div dir="rtl" lang="ar">
      <Header />
      <main>
        <Hero />
        <Marquee />
        <Intro />
        <HowItWorks />
        <Categories />
        <Benefits />
        <Calculator />
        <AppPreview />
        <FAQ />
        <VendorSignup />
      </main>
      <Footer />
    </div>
  );
}
