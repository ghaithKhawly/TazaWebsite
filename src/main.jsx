import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  BadgeCheck,
  ChartNoAxesColumnIncreasing,
  Check,
  Clock,
  Copy,
  LayoutList,
  Mail,
  MessageCircle,
  PackagePlus,
  QrCode,
  Send,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Store,
  Users,
} from "lucide-react";
import "../styles.css";

const categories = [
  {
    code: "01",
    icon: PackagePlus,
    title: "Bakeries",
    text: "Bread, pastries, croissants, and fresh case items near closing.",
  },
  {
    code: "02",
    icon: Store,
    title: "Restaurants",
    text: "Meals, prepared sides, and kitchen surplus before close.",
  },
  {
    code: "03",
    icon: ShoppingBag,
    title: "Grocers",
    text: "Produce, deli, pantry, and fresh stock with short selling windows.",
  },
  {
    code: "04",
    icon: BadgeCheck,
    title: "Dessert shops",
    text: "Cakes, sweets, cookies, and premium treats that should still sell.",
  },
  {
    code: "05",
    icon: Clock,
    title: "Cafes",
    text: "Coffee pairings, sandwiches, baked goods, and lunch case extras.",
  },
  {
    code: "06",
    icon: SlidersHorizontal,
    title: "Specialty shops",
    text: "Juice bars, small food vendors, and local niche food businesses.",
  },
];

const steps = [
  {
    icon: PackagePlus,
    title: "List a Surprise Basket",
    text: "Set quantity, value, price, and pickup window. Your team keeps control of what goes inside.",
  },
  {
    icon: Users,
    title: "Customers reserve nearby",
    text: "Taza shows the offer to local food-curious customers looking for value and discovery.",
  },
  {
    icon: QrCode,
    title: "Pickup is confirmed",
    text: "The customer comes to your shop, shows a code, and staff marks the basket collected.",
  },
];

const benefits = [
  {
    icon: ShieldCheck,
    title: "No public discount shelf",
    text: "Your full-price menu stays protected. Taza sells a basket offer, not individual markdowns.",
  },
  {
    icon: SlidersHorizontal,
    title: "Vendor-controlled",
    text: "You decide contents, quantity, pickup time, availability, and whether to list at all.",
  },
  {
    icon: Clock,
    title: "Built for closing time",
    text: "The flow is short enough for a busy team: create basket, pack basket, confirm pickup.",
  },
  {
    icon: ChartNoAxesColumnIncreasing,
    title: "Recover real revenue",
    text: "Turn food you already made into extra sales and potential repeat customers.",
  },
];

const appCards = [
  {
    icon: LayoutList,
    label: "Customer",
    title: "Nearby basket feed",
    text: "Customers see shop, category, value, pickup window, and quantity left.",
  },
  {
    icon: ShoppingBag,
    label: "Customer",
    title: "Basket detail",
    text: "Surprise stays exciting, while key facts like value, timing, and notes stay clear.",
  },
  {
    icon: PackagePlus,
    label: "Vendor",
    title: "Create basket",
    text: "A short form for quantity, price, pickup window, and any dietary or pickup notes.",
  },
  {
    icon: BadgeCheck,
    label: "Vendor",
    title: "Confirm pickup",
    text: "Use the customer's code to mark the basket collected and keep orders organized.",
  },
];

const pilotSteps = [
  {
    title: "Send shop details",
    text: "Share category, area, contact number, closing time, and the surplus you usually see.",
  },
  {
    title: "Choose the first basket",
    text: "Agree on value, price, quantity, pickup window, and any simple dietary notes.",
  },
  {
    title: "Run a test window",
    text: "Your team prepares only reserved baskets. Customers pick up in store with a code.",
  },
  {
    title: "Learn from real orders",
    text: "Track pickup timing, customer response, and whether the pilot should expand.",
  },
];

const faqs = [
  {
    question: "Will Taza cheapen my brand?",
    answer:
      "No. The offer is framed as a limited Surprise Basket, not a public discount bin or item-by-item sale.",
  },
  {
    question: "Do we need delivery?",
    answer:
      "No. Taza is pickup only. Customers come to your shop during the pickup window you choose.",
  },
  {
    question: "Who decides what goes inside?",
    answer:
      "The vendor does. Taza gives you a flexible basket format so you can move the fresh surplus you actually have.",
  },
  {
    question: "Will this hurt full-price sales?",
    answer:
      "Taza is positioned for end-of-day surplus and limited availability, not as a replacement for your regular menu.",
  },
  {
    question: "What if nothing sells?",
    answer:
      "You only list what you want to offer. If a basket does not sell, there is no delivery route or extra fulfillment burden.",
  },
  {
    question: "Is this an app or a manual pilot?",
    answer:
      "The page is ready for vendor validation now. The flow can start with a manual or semi-manual pilot while the product matures.",
  },
];

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function Brand() {
  return (
    <a className="brand" href="#top" aria-label="Taza home">
      <span className="brand-emblem" aria-hidden="true">
        <span className="brand-letter">T</span>
        <span className="brand-leaf" />
      </span>
      <span className="brand-copy">
        <span className="brand-name">Taza</span>
        <span className="brand-tagline">Save the food. Save the mood.</span>
      </span>
    </a>
  );
}

function Header() {
  return (
    <header className="site-header">
      <Brand />
      <nav className="site-nav" aria-label="Main navigation">
        <a href="#how">How it works</a>
        <a href="#vendors">For vendors</a>
        <a href="#app">App flow</a>
        <a href="#join">Join</a>
      </nav>
      <a className="nav-cta" href="#join">
        Become a vendor
      </a>
    </header>
  );
}

function ButtonLink({ href, variant = "primary", children }) {
  return (
    <a className={`button button-${variant}`} href={href}>
      <span>{children}</span>
      {variant === "primary" ? <ArrowRight size={18} strokeWidth={2.2} /> : null}
    </a>
  );
}

function ProductMockup() {
  return (
    <div className="product-mockup" aria-label="Taza app and vendor dashboard preview">
      <div className="mockup-heading">
        <span>Vendor view</span>
        <strong>Tonight: 6 baskets live</strong>
      </div>
      <div className="basket-preview">
        <div>
          <span className="status-dot" />
          <p>Bakery Surprise Basket</p>
          <h3>Evening pastry mix</h3>
          <small>3 left - pickup 8:30-9:15 PM</small>
        </div>
        <div className="price-block">
          <span>$18 value</span>
          <strong>$6</strong>
        </div>
      </div>
      <div className="dashboard-grid">
        <div>
          <span>Reserved</span>
          <strong>9</strong>
        </div>
        <div>
          <span>Pickup code</span>
          <strong>TZ-42</strong>
        </div>
        <div>
          <span>Recovered</span>
          <strong>$54</strong>
        </div>
      </div>
      <div className="vendor-note">
        <ShieldCheck size={18} />
        <span>No delivery. No public menu discount. Vendor controls the basket.</span>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="hero section-wrap" id="top">
      <div className="hero-copy">
        <p className="eyebrow">Founding vendor pilot</p>
        <h1>Turn surplus into extra revenue.</h1>
        <p>
          Taza helps restaurants, bakeries, cafes, and local stores turn end-of-day surplus into
          pickup-only Surprise Baskets. You set the window, quantity, and contents. Customers
          reserve nearby and collect in store.
        </p>
        <div className="hero-actions">
          <ButtonLink href="#join">Become a founding vendor</ButtonLink>
          <ButtonLink href="#how" variant="secondary">
            See how it works
          </ButtonLink>
        </div>
        <ul className="hero-points" aria-label="Taza vendor advantages">
          <li>
            <Check size={16} strokeWidth={2.4} />
            No delivery setup
          </li>
          <li>
            <Check size={16} strokeWidth={2.4} />
            No public item discounts
          </li>
          <li>
            <Check size={16} strokeWidth={2.4} />
            Shop controls the basket
          </li>
        </ul>
      </div>
      <ProductMockup />
    </section>
  );
}

function ProofBar() {
  return (
    <section className="proof-bar" aria-label="Taza promise">
      <div>
        <strong>Pickup only</strong>
        <span>No driver logistics or delivery setup.</span>
      </div>
      <div>
        <strong>No public markdowns</strong>
        <span>Move surplus without public markdowns.</span>
      </div>
      <div>
        <strong>Vendor controlled</strong>
        <span>You choose the contents and timing.</span>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="section section-light" id="how">
      <div className="section-heading">
        <p className="section-kicker">How it works</p>
        <h2>A simple closing-time flow, not another delivery system.</h2>
      </div>
      <div className="steps-grid">
        {steps.map(({ icon: Icon, title, text }) => (
          <article className="info-card" key={title}>
            <Icon size={24} strokeWidth={2.2} />
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function VendorBenefits() {
  return (
    <section className="section vendor-section" id="vendors">
      <div className="section-heading">
        <p className="section-kicker">Why vendors care</p>
        <h2>Revenue-first, brand-safe, operationally light.</h2>
        <p>
          Taza is built for fresh food businesses that want to recover value from food they already
          made while keeping the regular menu, pickup timing, and customer experience under control.
        </p>
      </div>
      <div className="benefit-grid">
        {benefits.map(({ icon: Icon, title, text }) => (
          <article className="dark-card" key={title}>
            <Icon size={24} strokeWidth={2.2} />
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Categories() {
  return (
    <section className="section" id="categories">
      <div className="section-heading">
        <p className="section-kicker">Vendor categories</p>
        <h2>Built for the food businesses with the most end-of-day upside.</h2>
      </div>
      <div className="category-grid">
        {categories.map(({ code, icon: Icon, title, text }) => (
          <article className="category-card" key={title}>
            <span>{code}</span>
            <Icon size={22} strokeWidth={2.1} />
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function RevenueCalculator() {
  const [values, setValues] = useState({ baskets: 6, price: 7, days: 25 });
  const total = useMemo(
    () => values.baskets * values.price * values.days,
    [values.baskets, values.price, values.days],
  );

  function updateValue(event) {
    setValues((current) => ({
      ...current,
      [event.target.name]: Number(event.target.value) || 0,
    }));
  }

  return (
    <section className="section calculator" id="calculator">
      <div className="calculator-copy">
        <p className="section-kicker">Quick estimate</p>
        <h2>Show the upside in seconds.</h2>
        <p>
          Try a conservative estimate before you join. Even a few baskets per day can turn fresh
          surplus into measurable monthly revenue.
        </p>
      </div>
      <form className="calc-panel">
        <label>
          Baskets per day
          <input name="baskets" type="number" min="1" max="50" value={values.baskets} onChange={updateValue} />
        </label>
        <label>
          Average basket price
          <input name="price" type="number" min="1" max="200" value={values.price} onChange={updateValue} />
        </label>
        <label>
          Days open per month
          <input name="days" type="number" min="1" max="31" value={values.days} onChange={updateValue} />
        </label>
        <div className="calc-result">
          <span>Estimated recovered revenue</span>
          <output>{currency.format(total)}</output>
          <small>Before commission. No delivery fleet. No public menu discount.</small>
        </div>
      </form>
    </section>
  );
}

function AppPreview() {
  return (
    <section className="section section-light" id="app">
      <div className="section-heading">
        <p className="section-kicker">Product flow</p>
        <h2>The flow customers and vendors can trust.</h2>
      </div>
      <div className="app-grid">
        {appCards.map(({ icon: Icon, label, title, text }) => (
          <article className="info-card" key={title}>
            <div className="card-topline">
              <Icon size={22} strokeWidth={2.2} />
              <span>{label}</span>
            </div>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function FAQ() {
  return (
    <section className="section" id="faq">
      <div className="section-heading">
        <p className="section-kicker">Vendor objections</p>
        <h2>Answers before you join.</h2>
      </div>
      <div className="faq-list">
        {faqs.map(({ question, answer }) => (
          <details key={question}>
            <summary>{question}</summary>
            <p>{answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function PilotPlan() {
  return (
    <section className="section pilot-section" id="pilot">
      <div className="section-heading">
        <p className="section-kicker">After you scan</p>
        <h2>A practical pilot path for busy shops.</h2>
        <p>
          Taza can start lean: validate surplus, test customer pickup, and learn what works before a
          shop commits to a deeper product rollout.
        </p>
      </div>
      <div className="pilot-grid">
        {pilotSteps.map(({ title, text }, index) => (
          <article className="pilot-card" key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function VendorSignup() {
  const [form, setForm] = useState({
    shop: "",
    category: "",
    area: "",
    whatsapp: "",
    closing: "",
    surplus: "",
  });
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);

  function handleChange(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextMessage = [
      "Hi Taza, I want to join as a founding vendor.",
      "",
      `Shop: ${form.shop}`,
      `Category: ${form.category}`,
      `Area/city: ${form.area}`,
      `WhatsApp: ${form.whatsapp || "-"}`,
      `Average closing time: ${form.closing || "-"}`,
      `Surplus type: ${form.surplus || "-"}`,
    ].join("\n");
    setMessage(nextMessage);
  }

  async function copyMessage() {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  const whatsappHref = `https://wa.me/?text=${encodeURIComponent(message)}`;

  return (
    <section className="section join" id="join">
      <div className="join-copy">
        <p className="section-kicker">Founding vendor pilot</p>
        <h2>Join Taza as a founding vendor.</h2>
        <p>
          Send the key details in under a minute. The message opens in WhatsApp so founder outreach,
          shop visits, and QR traffic can move straight into a real conversation.
        </p>
        <div className="contact-options">
          <a href="https://wa.me/?text=Hi%20Taza%2C%20I%20want%20to%20join%20as%20a%20vendor." target="_blank" rel="noreferrer">
            <MessageCircle size={17} />
            WhatsApp
          </a>
          <a href="https://t.me/" target="_blank" rel="noreferrer">
            <Send size={17} />
            Telegram
          </a>
          <a href="mailto:hello@taza.local?subject=Taza%20vendor%20interest">
            <Mail size={17} />
            Email
          </a>
        </div>
      </div>

      <form className="signup-form" onSubmit={handleSubmit}>
        <h3>Vendor interest</h3>
        <div className="form-grid">
          <label>
            Shop name
            <input name="shop" autoComplete="organization" value={form.shop} onChange={handleChange} required />
          </label>
          <label>
            Category
            <select name="category" value={form.category} onChange={handleChange} required>
              <option value="">Select one</option>
              <option>Restaurant</option>
              <option>Bakery</option>
              <option>Cafe</option>
              <option>Sweet shop</option>
              <option>Grocery or pantry</option>
              <option>Juice or beverages</option>
              <option>Other food business</option>
            </select>
          </label>
          <label>
            Area or city
            <input name="area" autoComplete="address-level2" value={form.area} onChange={handleChange} required />
          </label>
          <label>
            WhatsApp number
            <input name="whatsapp" inputMode="tel" autoComplete="tel" value={form.whatsapp} onChange={handleChange} />
          </label>
          <label>
            Average closing time
            <input name="closing" placeholder="Example: 10:00 PM" value={form.closing} onChange={handleChange} />
          </label>
          <label>
            Surplus type
            <input name="surplus" placeholder="Example: pastries, meals, bread" value={form.surplus} onChange={handleChange} />
          </label>
        </div>
        <button className="button button-primary" type="submit">
          <span>Create vendor message</span>
          <ArrowRight size={18} strokeWidth={2.2} />
        </button>
        {message ? (
          <div className="form-output">
            <h3>Vendor message ready</h3>
            <p>{message}</p>
            <div className="output-actions">
              <button className="button button-secondary" type="button" onClick={copyMessage}>
                {copied ? <Check size={18} /> : <Copy size={18} />}
                {copied ? "Copied" : "Copy message"}
              </button>
              <a className="button button-primary" href={whatsappHref} target="_blank" rel="noreferrer">
                Send on WhatsApp
              </a>
            </div>
          </div>
        ) : null}
      </form>
    </section>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <div>
        <Brand />
        <p>Fresh surplus. Local pickup. Limited daily baskets.</p>
      </div>
      <a href="#top">Back to top</a>
    </footer>
  );
}

function App() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <ProofBar />
        <HowItWorks />
        <VendorBenefits />
        <Categories />
        <RevenueCalculator />
        <AppPreview />
        <FAQ />
        <PilotPlan />
        <VendorSignup />
      </main>
      <Footer />
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
