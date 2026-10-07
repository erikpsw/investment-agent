"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { homeEnglish, type HomeText } from "@/lib/home-locales";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Activity,
  ChartNoAxesCombined,
  ScanLine,
  Layers3,
  BriefcaseBusiness,
  FileChartColumn,
  Sparkles,
  Globe2,
  Crosshair,
  Star,
} from "lucide-react";
import styles from "./landing.module.css";

const features = [
  {
    icon: ChartNoAxesCombined,
    number: "01",
    title: "市场全景",
    text: "连接 A 股、港股与美股，从市场热点发现下一条研究线索。",
    href: "/dashboard",
    action: "打开市场仪表盘",
    tag: "MARKET INTELLIGENCE",
  },
  {
    icon: Sparkles,
    number: "02",
    title: "AI 个股研究",
    text: "从行情到基本面，让 Agent 帮你拆解公司，深入理解投资逻辑。",
    href: "/stock",
    action: "开始个股分析",
    tag: "AGENT RESEARCH",
  },
  {
    icon: Crosshair,
    number: "03",
    title: "智能条件选股",
    text: "把投资想法变成筛选条件，在纷繁的市场中缩小研究范围。",
    href: "/stock-picker",
    action: "探索选股工具",
    tag: "OPPORTUNITY DISCOVERY",
  },
  {
    icon: Activity,
    number: "04",
    title: "自选与盯盘",
    text: "聚焦你关心的标的，追踪行情变化，让重要信号更清晰。",
    href: "/watchlist/monitor",
    action: "进入实时盯盘",
    tag: "SIGNAL MONITOR",
  },
  {
    icon: BriefcaseBusiness,
    number: "05",
    title: "投资组合",
    text: "从单一标的走向整体视角，审视持仓结构与组合表现。",
    href: "/portfolio",
    action: "查看投资组合",
    tag: "PORTFOLIO INSIGHT",
  },
  {
    icon: Layers3,
    number: "06",
    title: "板块与财报",
    text: "观察行业轮动，深入财务数据，为研究补上更完整的拼图。",
    href: "/sectors",
    action: "探索板块分析",
    tag: "FUNDAMENTAL EXPLORER",
  },
];

const languageKey = "investment-agent-language";
function subscribeLanguage(onChange: () => void) {
  const onStorage = () => {
    currentLanguage = undefined;
    onChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("investment-language-change", onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("investment-language-change", onChange);
  };
}
let currentLanguage: "zh" | "en" | undefined;
function getLanguage() {
  if (currentLanguage) return currentLanguage;
  try {
    return localStorage.getItem(languageKey) === "en" ? "en" : "zh";
  } catch {
    return "zh";
  }
}

export default function HomePage() {
  const [activeSection, setActiveSection] = useState("overview");
  useEffect(() => {
    const updateSection = () => {
      const sections = ["overview", "capabilities", "workflow"];
      const current = sections
        .filter(
          (id) =>
            (document.getElementById(id)?.getBoundingClientRect().top ??
              Infinity) <=
            window.innerHeight * 0.4,
        )
        .at(-1);
      setActiveSection(current ?? "overview");
    };
    updateSection();
    window.addEventListener("scroll", updateSection, { passive: true });
    window.addEventListener("resize", updateSection);
    return () => {
      window.removeEventListener("scroll", updateSection);
      window.removeEventListener("resize", updateSection);
    };
  }, []);
  const locale = useSyncExternalStore(
    subscribeLanguage,
    getLanguage,
    () => "zh",
  );
  const t = (text: string) =>
    locale === "en" ? (homeEnglish[text as HomeText] ?? text) : text;
  const toggleLanguage = () => {
    currentLanguage = locale === "zh" ? "en" : "zh";
    try {
      localStorage.setItem(languageKey, currentLanguage);
    } catch {
      /* Session switching still works without storage. */
    }
    window.dispatchEvent(new Event("investment-language-change"));
  };
  return (
    <div
      className={styles.landing}
      lang={locale === "zh" ? "zh-CN" : "en"}
      data-locale={locale}
    >
      <header className={styles.header}>
        <Link
          href="/"
          className={styles.brand}
          aria-label={t("Investment Agent 首页")}
        >
          <span className={styles.logo}>
            <ChartNoAxesCombined size={22} />
          </span>
          Investment<span className={styles.brandLight}>Agent</span>
          <span className={styles.beta}>BETA</span>
        </Link>
        <nav className={styles.nav} aria-label={t("主页导航")}>
          <a href="#capabilities">{t("产品能力")}</a>
          <a href="#workflow">{t("研究工作流")}</a>
        </nav>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.languageSwitch}
            onClick={toggleLanguage}
            aria-label={locale === "zh" ? "Switch to English" : "切换为中文"}
          >
            <Globe2 size={14} />
            {locale === "zh" ? "EN" : "中文"}
          </button>
          <Link href="/dashboard" prefetch={false} className={styles.navCta}>
            {t("进入工作台")} <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>

      <nav className={styles.sideNav} aria-label={t("快捷导航")}>
        <span className={styles.sideNavTitle}>EXPLORE</span>
        {[
          { id: "overview", label: "产品概览", icon: Globe2 },
          { id: "capabilities", label: "产品能力", icon: Layers3 },
          { id: "workflow", label: "研究工作流", icon: ScanLine },
        ].map((item, i) => (
          <a
            key={item.id}
            href={`#${item.id}`}
            aria-current={activeSection === item.id ? "location" : undefined}
          >
            <item.icon size={17} />
            <span>{t(item.label)}</span>
            <small>0{i + 1}</small>
          </a>
        ))}
        <div className={styles.sideNavDivider} />
        <Link href="/stock" prefetch={false}>
          <Sparkles size={17} />
          <span>{t("个股研究")}</span>
          <ArrowUpRight size={13} />
        </Link>
        <Link
          href="/dashboard"
          prefetch={false}
          className={styles.sideNavWorkspace}
        >
          <ChartNoAxesCombined size={17} />
          <span>{t("进入工作台")}</span>
          <ArrowUpRight size={13} />
        </Link>
      </nav>
      <main>
        <section id="overview" className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span /> YOUR NEXT-GEN INVESTMENT COPILOT
            </div>
            <h1>
              {t("洞察先行。")}
              <br />
              {t("让投资，")}
              <br />
              <em>{t("多一份智慧。")}</em>
            </h1>
            <p className={styles.description}>
              {t("你的 AI 投资研究搭档。连接市场、数据与推理，")}
              <br className={styles.desktopBreak} />{" "}
              {t("把纷繁的信息，转化为更清晰的投资视角。")}
            </p>
            <div className={styles.actions}>
              <Link href="/dashboard" prefetch={false} className={styles.primary}>
                {t("开始投资研究")} <ArrowUpRight size={19} />
              </Link>
              <a href="#capabilities" className={styles.secondary}>
                {t("探索全部能力")} <ArrowRight size={17} />
              </a>
            </div>
            <div className={styles.heroMeta}>
              <span>
                <Globe2 size={14} /> {t("A 股 / 港股 / 美股")}
              </span>
              <span>
                <Sparkles size={14} /> {t("AI 驱动研究")}
              </span>
            </div>
          </div>
          <div
            className={styles.visual}
            aria-label={t("Agent 研究流程概念演示")}
          >
            <div className={styles.visualTop}>
              <span>AGENT INTELLIGENCE ENGINE</span>
              <span className={styles.demo}>{t("概念演示")}</span>
            </div>
            <div
              className={styles.orbitScene}
              onPointerMove={(event) => {
                if (
                  event.pointerType !== "mouse" ||
                  window.matchMedia("(prefers-reduced-motion: reduce)").matches
                )
                  return;
                const bounds = event.currentTarget.getBoundingClientRect();
                event.currentTarget.style.setProperty(
                  "--tilt-x",
                  `${-(event.clientY - bounds.top - bounds.height / 2) / 24}deg`,
                );
                event.currentTarget.style.setProperty(
                  "--tilt-y",
                  `${(event.clientX - bounds.left - bounds.width / 2) / 24}deg`,
                );
              }}
              onPointerLeave={(event) => {
                event.currentTarget.style.setProperty("--tilt-x", "0deg");
                event.currentTarget.style.setProperty("--tilt-y", "0deg");
              }}
            >
              <div className={styles.floorGlow} aria-hidden="true" />
              <div className={styles.scene3d}>
                <div className={styles.orbitOuter} />
                <div className={styles.orbitMiddle} />
                <div className={styles.orbitInner} />
                <div className={styles.axisX} />
                <div className={styles.axisY} />
                <div className={styles.core}>
                  <div className={styles.sphereGrid} aria-hidden="true">
                    <i />
                    <i />
                    <i />
                    <i />
                    <i />
                  </div>
                  <Sparkles size={40} strokeWidth={1.2} />
                  <strong>Agent</strong>
                  <small>THINK · CONNECT · DISCOVER</small>
                </div>
                <div className={`${styles.node} ${styles.nodeOne}`}>
                  <Globe2 size={17} />
                  <span>
                    {t("市场感知")}
                    <small>MARKET</small>
                  </span>
                </div>
                <div className={`${styles.node} ${styles.nodeTwo}`}>
                  <FileChartColumn size={17} />
                  <span>
                    {t("深度研究")}
                    <small>RESEARCH</small>
                  </span>
                </div>
                <div className={`${styles.node} ${styles.nodeThree}`}>
                  <ScanLine size={17} />
                  <span>
                    {t("信号发现")}
                    <small>SIGNAL</small>
                  </span>
                </div>
                <span className={styles.orbitDot} />
              </div>
            </div>
            <div className={styles.terminal}>
              <div>
                <span className={styles.terminalDot} />
                RESEARCH WORKFLOW{" "}
                <span className={styles.terminalLabel}>{t("流程预览")}</span>
              </div>
              <p>
                <span>01</span> {t("汇集市场与基本面信息")}{" "}
                <span className={styles.done}>{t("数据")}</span>
              </p>
              <p>
                <span>02</span> {t("关联线索，构建研究视角")}{" "}
                <span className={styles.done}>{t("推理")}</span>
              </p>
              <p>
                <span>03</span> {t("生成可进一步探索的分析")}{" "}
                <ArrowUpRight size={14} />
              </p>
            </div>
          </div>
        </section>

        <div className={styles.marketStrip}>
          <span className={styles.stripLabel}>
            ONE WORKSPACE.
            <br />
            <strong>MORE PERSPECTIVES.</strong>
          </span>
          <span>
            CN <b>{t("A 股市场")}</b>
          </span>
          <span>
            HK <b>{t("港股市场")}</b>
          </span>
          <span>
            US <b>{t("美股市场")}</b>
          </span>
          <span className={styles.stripEnd}>
            {t("连接数据，拓宽视野")} <ArrowUpRight size={18} />
          </span>
        </div>

        <section id="capabilities" className={styles.capabilities}>
          <div className={styles.sectionHeading}>
            <div>
              <div className={styles.kicker}>
                BUILT FOR YOUR INVESTMENT JOURNEY
              </div>
              <h2>{t("从一个问题，到更完整的判断。")}</h2>
            </div>
            <p>
              {t("让每一步研究，都有工具可依。")}
              <br />
              {t("选择一个入口，开启你的探索。")}
            </p>
          </div>
          <div className={styles.grid}>
            {features.map((feature) => (
              <article key={feature.number} className={styles.card}>
                <div className={styles.cardTop}>
                  <feature.icon size={24} strokeWidth={1.5} />
                  <span>{feature.number}</span>
                </div>
                <small>{feature.tag}</small>
                <h3>{t(feature.title)}</h3>
                <p>{t(feature.text)}</p>
                <Link href={feature.href} prefetch={false}>
                  {t(feature.action)}
                  <ArrowUpRight size={17} />
                </Link>
              </article>
            ))}
          </div>
          <div className={styles.quickLinks}>
            <span>{t("还有更多研究工具")}</span>
            <Link href="/search" prefetch={false}>
              <ScanLine size={15} />
              {t("行情搜索")} <ArrowUpRight size={14} />
            </Link>
            <Link href="/watchlist" prefetch={false}>
              <Star size={15} />
              {t("我的自选")} <ArrowUpRight size={14} />
            </Link>
            <Link href="/financials" prefetch={false}>
              <FileChartColumn size={15} />
              {t("财报数据")} <ArrowUpRight size={14} />
            </Link>
          </div>
        </section>

        <section id="workflow" className={styles.workflow}>
          <div>
            <div className={styles.kicker}>LESS NOISE. MORE CLARITY.</div>
            <h2>
              {t("研究有章法，")}
              <br />
              <span>{t("思考有空间。")}</span>
            </h2>
            <Link href="/dashboard" prefetch={false} className={styles.primary}>
              {t("开启你的工作台")} <ArrowUpRight size={18} />
            </Link>
          </div>
          <ol>
            {[
              {
                title: "发现值得关注的方向",
                text: "从市场全景与板块变化出发，建立你的观察列表。",
              },
              {
                title: "让 Agent 帮你深入一步",
                text: "结合个股分析与财报数据，验证你的研究假设。",
              },
              {
                title: "持续跟踪，迭代判断",
                text: "通过自选盯盘与组合视角，让研究保持连续。",
              },
            ].map((step, i) => (
              <li key={step.title}>
                <span>0{i + 1}</span>
                <div>
                  <h3>{t(step.title)}</h3>
                  <p>{t(step.text)}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>
      <footer className={styles.footer}>
        <span className={styles.footerBrand}>
          <ChartNoAxesCombined size={18} /> Investment Agent
        </span>
        <p>{t("AI 辅助研究 · 信息仅供参考，不构成投资建议")}</p>
        <span>THINK AHEAD. INVEST WITH CLARITY.</span>
      </footer>
    </div>
  );
}
