import React, { useEffect, useRef, useState } from "react";
import fullLogo from "./full-logo.jpg";
import appIcon from "./app-icon.png";
import "./TazaLanding.css";

/* ───────────────────────── Data ───────────────────────── */

const categories = [
  { icon: "🥐", title: "Bakery & Bread" },
  { icon: "🍔", title: "Fast Food" },
  { icon: "🍎", title: "Fruits & Vegetables" },
  { icon: "🥫", title: "Groceries & Pantry" },
  { icon: "🧁", title: "Sweets & Pastries" },
  { icon: "☕", title: "Coffee & Beverages" },
];

const steps = [
  {
    num: "01",
    title: "Create your basket",
    body: "Set category, quantity, pickup window, and price. You decide what goes inside based on what's fresh and ready at the end of the day.",
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
    ),
  },
  {
    num: "02",
    title: "Customers reserve it",
    body: "Nearby customers browse Taza, see your basket, and buy before it sells out. Limited supply creates real urgency and local discovery.",
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
  {
    num: "03",
    title: "They pick up at your shop",
    body: "No drivers. No delivery route. The customer arrives with a pickup code, your staff confirms, and the order is done.",
    icon: (
      <svg viewBox="0 0 24 24">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    ),
  },
];

const benefits = [
  {
    title: "Protect your brand",
    body: "Sell basket-based offers instead of public item-by-item discounts. Your menu stays full-price. Surplus moves privately through Taza.",
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    title: "Stay in full control",
    body: "You choose the basket contents, pickup window, quantity, and daily availability. Taza never dictates what goes inside.",
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
        <path d="M4.93 4.93a10 10 0 0 0 0 14.14" />
      </svg>
    ),
  },
  {
    title: "Keep operations light",
    body: "No delivery fleet, no new kitchen process, no inventory ownership. Taza brings the demand; your team packs the basket at closing.",
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    ),
  },
  {
    title: "Create new discovery",
    body: "Tonight's surplus basket becomes tomorrow's repeat customer. Taza users are food-curious, local, and likely to return.",
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
];

const screens = [
  { tag: "Browse", title: "Nearby baskets", body: "Customers filter by category, pickup time, distance, and price. They see your shop, rating, and basket value before buying." },
  { tag: "Reserve", title: "Basket details", body: "They see shop name, basket value, pickup window, dietary notes, and how many are left. Limited quantity drives fast action." },
  { tag: "Pickup", title: "Confirmation code", body: "The app generates a pickup code. Staff confirm it to mark the order collected. The exchange takes under 30 seconds." },
  { tag: "Vendor", title: "Create a basket", body: "Set category, quantity, pickup window, price. One simple form. Takes two minutes. Taza does the rest." },
  { tag: "Vendor", title: "Manage live orders", body: "See real-time reservations as they come in. Mark baskets picked up from your vendor dashboard — no extra hardware." },
  { tag: "Vendor", title: "View earnings", body: "Track daily, weekly, and monthly recovered revenue. A simple view shows exactly what Taza added to your bottom line." },
];

const faqs = [
  { q: "Will this make my shop look cheap?", a: "No. Taza uses Surprise Baskets, not a public discount shelf or item-by-item markdowns. Your regular menu stays full-price." },
  { q: "Do I need to set up delivery?", a: "Never. Taza is pickup only. Customers come to your location during your chosen pickup window." },
  { q: "Who controls what goes inside the basket?", a: "You do. The basket exists so your team can move the fresh surplus you actually have that day." },
  { q: "What if no one buys my basket?", a: "You only list what you choose to offer. If a basket goes unsold, you're in no worse a position than before." },
  { q: "Will this affect my full-price sales?", a: "Taza baskets are end-of-day only, listed near closing time. There's no reason to skip full-price menu items for a basket." },
  { q: "How do I get paid?", a: "Taza collects payment from the customer and transfers the vendor's share. Exact payment flow is confirmed during onboarding." },
];

const VENDOR_WHATSAPP = "31600000000"; // TODO: replace with real vendor WhatsApp number

/* ───────────────────────── Helpers ───────────────────────── */

function useFadeIn() {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.unobserve(el);
        }
      },
      { threshold: 0.12 }
    );
    observer.observe(el);
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

const ArrowIcon = () => (
  <svg viewBox="0 0 24 24">
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </svg>
);

/* ───────────────────────── Sections ───────────────────────── */

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
        <a href="#top" aria-label="Taza home">
          <img className="logo-img" src={fullLogo} alt="Taza logo" />
        </a>
        <nav className="nav">
          <a href="#how">How it works</a>
          <a href="#vendors">For vendors</a>
          <a href="#app">App preview</a>
          <a href="#faq">FAQ</a>
          <a href="#join">Join</a>
        </nav>
        <div className="header-cta">
          <a className="btn btn-dark" href="#join">
            Become a vendor
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
          <span className="kicker">Hyper-local food rescue marketplace</span>
          <h1 className="hero-title">
            Turn unsold food into
            <br />
            <em>extra revenue.</em>
          </h1>
          <p className="hero-sub">
            Restaurants, bakeries, cafes, and sweet shops sell fresh end-of-day surplus as
            Surprise Baskets. Customers pick up near closing time. No delivery. No waste.
          </p>
          <div className="hero-actions">
            <a className="btn btn-white" href="#join">
              Become a founding vendor
              <ArrowIcon />
            </a>
            <a className="btn btn-outline" href="#how">
              See how it works
            </a>
          </div>
          <div className="trust-row">
            <span className="trust-chip">No delivery fleet</span>
            <span className="trust-chip">No public discount shelf</span>
            <span className="trust-chip">You control the basket</span>
            <span className="trust-chip">Pickup only</span>
          </div>
        </div>

        <div className="hero-phone-wrap">
          <div className="phone-frame">
            <div className="phone-notch" />
            <div className="phone-app-bar">
              <span className="phone-brand">Taza</span>
              <span className="phone-pill">6 baskets nearby</span>
            </div>
            <div className="phone-card">
              <div className="phone-card-label">Bakery Surprise Basket</div>
              <div className="phone-card-title">Evening pastry mix</div>
              <div className="phone-card-time">Pickup today, 8:30 – 9:15 PM</div>
              <div className="phone-price-row">
                <span className="phone-orig">€18 value</span>
                <span className="phone-price">€6</span>
              </div>
            </div>
            <div className="phone-row">
              <span>Stock remaining</span>
              <strong>3 left</strong>
            </div>
            <div className="phone-row">
              <span>Pickup code</span>
              <strong>TAZA-42</strong>
            </div>
            <div className="phone-qr">
              {Array.from({ length: 20 }, (_, i) => <span key={i} />)}
            </div>
          </div>
          <div className="phone-badge">
            <strong>No delivery setup.</strong>
            Customers come to you.
          </div>
        </div>
      </div>
    </section>
  );
}

function Marquee() {
  const items = [
    "Turn surplus into revenue",
    "No delivery fleet",
    "Pickup only",
    "You control the basket",
    "Save the food. Save the mood.",
    "Bakeries · Cafes · Restaurants",
    "Fresh end-of-day surplus",
  ];
  const loop = [...items, ...items];

  return (
    <div className="marquee-wrap" aria-hidden="true">
      <div className="marquee-track">
        {loop.map((text, i) => (
          <span key={i}>
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
          The simple model
        </FadeIn>
        <FadeIn as="h2" className="section-title">
          Fresh surplus becomes a <br />
          Surprise Basket.
        </FadeIn>
        <FadeIn as="p" className="section-body intro-body">
          Customers know the shop, pickup window, category, basket value, and price. The exact
          items stay flexible — so vendors move what is fresh and unsold without discounting
          their public menu item by item.
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
          <span className="kicker">How Taza works</span>
          <h2 className="section-title how-title">Three steps. Built for closing-time reality.</h2>
        </FadeIn>
        <div className="steps-grid">
          {steps.map((s) => (
            <FadeIn as="div" className="step-card" key={s.num}>
              <div className="step-num">{s.num}</div>
              <div className="step-icon">{s.icon}</div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
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
          <span className="kicker">Vendor categories</span>
          <h2 className="section-title">Made for local food businesses.</h2>
        </FadeIn>
        <div className="cat-grid">
          {categories.map((c) => (
            <FadeIn as="div" className="cat-card" key={c.title}>
              <div className="cat-icon">{c.icon}</div>
              <h3>{c.title}</h3>
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
          <span className="kicker kicker-white">For restaurants & stores</span>
          <h2 className="section-title section-title--white">
            Revenue first.
            <br />
            Waste reduction as the bonus.
          </h2>
          <p className="section-body section-body--white">
            Taza is designed to help food businesses recover value from food they already made —
            brand-safe, no delivery hassle, full vendor control.
          </p>
          <div className="benefits-cta">
            <a className="btn btn-white" href="#join">
              Join as a founding vendor
              <ArrowIcon />
            </a>
          </div>
        </FadeIn>
        <div className="benefits-grid">
          {benefits.map((b) => (
            <FadeIn as="div" className="benefit-card" key={b.title}>
              <div className="benefit-icon">{b.icon}</div>
              <h3>{b.title}</h3>
              <p>{b.body}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function Calculator() {
  const [baskets, setBaskets] = useState(6);
  const [price, setPrice] = useState(7);
  const [days, setDays] = useState(25);

  const total = baskets * price * days;
  const formatted = new Intl.NumberFormat("en-EU", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(total || 0);

  return (
    <section className="calculator" id="calculator">
      <div className="wrap calc-inner">
        <FadeIn>
          <span className="kicker">Quick revenue estimate</span>
          <h2 className="section-title">What could your surplus recover?</h2>
          <p className="section-body">
            This is a simple estimate to help you picture the upside before you join the pilot.
            Adjust the inputs on the right to match your shop's reality.
          </p>
          <div className="calc-example">
            <p className="calc-example-label">
              Example: A bakery with 5 baskets at €7 each, 26 days a month
            </p>
            <p className="calc-example-value">€910 / month</p>
            <p className="calc-example-note">…from food that would otherwise go unsold.</p>
          </div>
        </FadeIn>

        <FadeIn as="div" className="calc-panel">
          <div className="calc-field">
            <label htmlFor="baskets">Baskets per day</label>
            <input
              id="baskets"
              type="number"
              min={1}
              max={50}
              value={baskets}
              onChange={(e) => setBaskets(Number(e.target.value) || 0)}
            />
          </div>
          <div className="calc-field">
            <label htmlFor="price">Average basket price (€)</label>
            <input
              id="price"
              type="number"
              min={1}
              max={200}
              value={price}
              onChange={(e) => setPrice(Number(e.target.value) || 0)}
            />
          </div>
          <div className="calc-field">
            <label htmlFor="days">Days open per month</label>
            <input
              id="days"
              type="number"
              min={1}
              max={31}
              value={days}
              onChange={(e) => setDays(Number(e.target.value) || 0)}
            />
          </div>
          <div className="calc-result-box">
            <span className="calc-result-label">Estimated monthly recovered revenue</span>
            <span className="calc-result-value">{formatted}</span>
            <span className="calc-note">Before Taza commission. No delivery cost. No extra staff.</span>
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
          <span className="kicker">What customers see</span>
          <h2 className="section-title">A clear buying flow that makes surprise feel safe.</h2>
        </FadeIn>
        <div className="screens-grid">
          {screens.map((s) => (
            <FadeIn as="div" className="screen-card" key={s.title}>
              <span className="screen-tag">{s.tag}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
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
          <span className="kicker">Common questions</span>
          <h2 className="section-title">Designed around real vendor concerns.</h2>
        </FadeIn>
        <div className="faq-grid">
          {faqs.map((f) => (
            <FadeIn as="details" className="faq-item" key={f.q}>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

type VendorForm = {
  shop: string;
  category: string;
  area: string;
  whatsapp: string;
  closing: string;
  surplus: string;
};

function VendorSignup() {
  const [form, setForm] = useState<VendorForm>({
    shop: "",
    category: "",
    area: "",
    whatsapp: "",
    closing: "",
    surplus: "",
  });
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);
  const outputRef = useRef<HTMLDivElement | null>(null);

  function update<K extends keyof VendorForm>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.shop || !form.category || !form.area) {
      window.alert("Please fill in at least your shop name, category, and city.");
      return;
    }

    const msg = [
      "Hi Taza! I want to join as a founding vendor.",
      "",
      `Shop: ${form.shop || "—"}`,
      `Category: ${form.category || "—"}`,
      `City/Area: ${form.area || "—"}`,
      `WhatsApp: ${form.whatsapp || "—"}`,
      `Closing time: ${form.closing || "—"}`,
      `Surplus type: ${form.surplus || "—"}`,
    ].join("\n");

    setMessage(msg);
    requestAnimationFrame(() => {
      outputRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  async function copyMessage() {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  const whatsappHref = `https://wa.me/${VENDOR_WHATSAPP}?text=${encodeURIComponent(message)}`;

  return (
    <section className="signup" id="join">
      <div className="wrap signup-inner">
        <FadeIn className="signup-copy">
          <span className="kicker kicker-white">Founding vendor pilot</span>
          <h2 className="section-title section-title--white">Want Taza for your shop?</h2>
          <p className="section-body section-body--white">
            Fill out the form and Taza will prepare a vendor setup message you can send by
            WhatsApp, Telegram, or email. We're onboarding founding vendors in pilot areas now.
          </p>
          <div className="contact-links">
            <a
              className="contact-link"
              href={`https://wa.me/${VENDOR_WHATSAPP}?text=${encodeURIComponent(
                "Hi Taza, I want to join as a founding vendor."
              )}`}
              target="_blank"
              rel="noreferrer"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              WhatsApp
            </a>
            <a className="contact-link" href="https://t.me/" target="_blank" rel="noreferrer">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              Telegram
            </a>
            <a className="contact-link" href="mailto:hello@taza.app?subject=Taza%20vendor%20interest">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              Email
            </a>
          </div>
        </FadeIn>

        <FadeIn as="div" className="form-box">
          <div className="form-title">Tell us about your shop</div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="f-shop">Shop name</label>
                <input
                  id="f-shop"
                  type="text"
                  placeholder="e.g. Sunrise Bakery"
                  autoComplete="organization"
                  value={form.shop}
                  onChange={(e) => update("shop", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-cat">Category</label>
                <select
                  id="f-cat"
                  value={form.category}
                  onChange={(e) => update("category", e.target.value)}
                >
                  <option value="">Select one</option>
                  <option>Restaurant</option>
                  <option>Bakery</option>
                  <option>Café</option>
                  <option>Sweet shop</option>
                  <option>Grocery or pantry</option>
                  <option>Juice or beverages</option>
                  <option>Other food business</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="f-area">City or area</label>
                <input
                  id="f-area"
                  type="text"
                  placeholder="e.g. Rotterdam"
                  autoComplete="address-level2"
                  value={form.area}
                  onChange={(e) => update("area", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-wa">WhatsApp number</label>
                <input
                  id="f-wa"
                  type="tel"
                  placeholder="+31 6 ..."
                  autoComplete="tel"
                  value={form.whatsapp}
                  onChange={(e) => update("whatsapp", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-close">Average closing time</label>
                <input
                  id="f-close"
                  type="text"
                  placeholder="e.g. 10:00 PM"
                  value={form.closing}
                  onChange={(e) => update("closing", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-surplus">Typical surplus</label>
                <input
                  id="f-surplus"
                  type="text"
                  placeholder="e.g. pastries, bread, meals"
                  value={form.surplus}
                  onChange={(e) => update("surplus", e.target.value)}
                />
              </div>
            </div>
            <button className="btn btn-dark form-submit" type="submit">
              Create vendor message
              <ArrowIcon />
            </button>
            <p className="form-note">No backend connected yet. This generates a ready-to-send signup message.</p>
          </form>

          {message ? (
            <div className="form-output-box visible" ref={outputRef}>
              <h4>Vendor message ready ✓</h4>
              <pre>{message}</pre>
              <div className="output-actions">
                <button className="btn btn-dark output-btn" type="button" onClick={copyMessage}>
                  {copied ? "Copied ✓" : "Copy message"}
                </button>
                <a className="btn output-btn output-btn--wa" href={whatsappHref} target="_blank" rel="noreferrer">
                  Send on WhatsApp
                </a>
              </div>
            </div>
          ) : null}
        </FadeIn>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer-inner">
          <div className="footer-brand">
            <img className="footer-logo" src={appIcon} alt="Taza" />
            <p className="footer-tagline">Fresh surplus. Local pickup. Limited daily baskets.</p>
          </div>
          <div className="footer-col">
            <h4>Product</h4>
            <ul>
              <li><a href="#how">How it works</a></li>
              <li><a href="#categories">Categories</a></li>
              <li><a href="#app">App preview</a></li>
              <li><a href="#calculator">Revenue calculator</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>Vendors</h4>
            <ul>
              <li><a href="#vendors">Why Taza</a></li>
              <li><a href="#faq">FAQ</a></li>
              <li><a href="#join">Become a vendor</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>Contact</h4>
            <ul>
              <li><a href={`https://wa.me/${VENDOR_WHATSAPP}`} target="_blank" rel="noreferrer">WhatsApp</a></li>
              <li><a href="https://t.me/" target="_blank" rel="noreferrer">Telegram</a></li>
              <li><a href="mailto:hello@taza.app">hello@taza.app</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Taza. Save the food. Save the mood.</span>
          <span>Made for local food businesses.</span>
        </div>
      </div>
    </footer>
  );
}

/* ───────────────────────── Page ───────────────────────── */

export default function TazaLanding() {
  return (
    <>
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
    </>
  );
}
