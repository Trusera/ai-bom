import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Img,
  staticFile,
} from "remotion";

// ─── Color palette (matches dashboard CSS) ──────────────────────
const BG = "#0d1117";
const CARD_BG = "#161b22";
const BORDER = "#30363d";
const TEXT = "#e6edf3";
const DIM = "#8b949e";
const ACCENT = "#58a6ff";
const GREEN = "#3fb950";
const YELLOW = "#d29922";
const RED = "#f85149";
const PURPLE = "#bc8cff";
const TEAL = "#2dd4bf";

// ─── Helpers ────────────────────────────────────────────────────
const showAfter = (frame: number, threshold: number) => frame >= threshold;

const typeText = (
  text: string,
  frame: number,
  startFrame: number,
  charsPerFrame = 0.5
) => {
  const elapsed = Math.max(0, frame - startFrame);
  const chars = Math.floor(elapsed * charsPerFrame);
  return text.slice(0, Math.min(chars, text.length));
};

const sevColor = (sev: string) => {
  switch (sev) {
    case "critical":
      return RED;
    case "high":
      return YELLOW;
    case "medium":
      return ACCENT;
    default:
      return GREEN;
  }
};

// ─── Cursor blink ───────────────────────────────────────────────
const Cursor: React.FC = () => {
  const frame = useCurrentFrame();
  const blink = Math.floor(frame / 8) % 2 === 0;
  return <span style={{ color: GREEN, opacity: blink ? 1 : 0 }}>|</span>;
};

// ─── Trusera Logo SVG ───────────────────────────────────────────
const TruseraLogo: React.FC<{ size?: number }> = ({ size = 64 }) => (
  <svg
    viewBox="0 0 64 64"
    width={size}
    height={size}
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M32 4L56 18V46L32 60L8 46V18L32 4Z"
      fill="#0F172A"
      stroke={ACCENT}
      strokeWidth="2"
    />
    <text
      x="32"
      y="40"
      textAnchor="middle"
      fontFamily="Arial,sans-serif"
      fontSize="28"
      fontWeight="bold"
      fill={ACCENT}
    >
      T
    </text>
  </svg>
);

// ─── Badge component ────────────────────────────────────────────
const Badge: React.FC<{ sev: string; small?: boolean }> = ({
  sev,
  small,
}) => (
  <span
    style={{
      display: "inline-block",
      padding: small ? "1px 6px" : "2px 8px",
      borderRadius: 12,
      fontSize: small ? 9 : 11,
      fontWeight: 700,
      color: sevColor(sev),
      background: `${sevColor(sev)}22`,
      border: `1px solid ${sevColor(sev)}44`,
      textTransform: "uppercase",
      letterSpacing: 0.5,
    }}
  >
    {sev}
  </span>
);

// ─── Stat card ──────────────────────────────────────────────────
const StatCard: React.FC<{
  value: string;
  label: string;
  color: string;
  opacity: number;
}> = ({ value, label, color, opacity }) => (
  <div
    style={{
      background: CARD_BG,
      border: `1px solid ${BORDER}`,
      borderRadius: 8,
      padding: "10px 14px",
      textAlign: "center",
      opacity,
      flex: 1,
    }}
  >
    <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
    <div style={{ fontSize: 10, color: DIM, marginTop: 2 }}>{label}</div>
  </div>
);

// ─── Findings data (realistic n8n scan) ─────────────────────────
const findings = [
  {
    name: "OpenAI Chat Model",
    type: "llm_provider",
    sev: "critical",
    score: 60,
    flags: ["hardcoded_api_key", "deprecated_model"],
    workflow: "AI Customer Support",
  },
  {
    name: "AI Agent",
    type: "agent_framework",
    sev: "critical",
    score: 55,
    flags: ["code_http_tools", "webhook_no_auth"],
    workflow: "AI Agent with Tools",
  },
  {
    name: "MCP Client",
    type: "mcp_client",
    sev: "medium",
    score: 35,
    flags: ["mcp_unknown_server", "no_rate_limit"],
    workflow: "Data Pipeline Agent",
  },
  {
    name: "Anthropic Model",
    type: "llm_provider",
    sev: "high",
    score: 45,
    flags: ["hardcoded_credentials", "no_error_handling"],
    workflow: "Content Generator",
  },
  {
    name: "HTTP Tool",
    type: "tool",
    sev: "medium",
    score: 30,
    flags: ["internet_facing", "no_auth"],
    workflow: "AI Agent with Tools",
  },
];

// ─── Remediation card data ──────────────────────────────────────
const remediationCards = [
  {
    flag: "hardcoded_api_key",
    sev: "critical",
    owasp: "LLM06: Excessive Agency",
    desc: "An AI provider API key is hardcoded in the workflow JSON instead of using n8n credentials.",
    fix: "Move the API key to n8n Credentials (Settings → Credentials) and rotate the exposed key immediately.",
    guardrail:
      "Enable a pre-commit hook that scans for API key patterns (sk-*, sk-ant-*) in workflow exports.",
  },
  {
    flag: "code_http_tools",
    sev: "critical",
    owasp: "LLM04: Output Handling",
    desc: "Agent has access to both code execution and HTTP request tools — can run arbitrary code and exfiltrate data.",
    fix: "Separate code execution and HTTP tools into different workflows. Add an approval step between them.",
    guardrail:
      "Implement an output filter blocking agent from sending code results to external URLs.",
  },
];

// ─── n8n workflow editor mockup ─────────────────────────────────
const N8nEditorMockup: React.FC<{ opacity: number }> = ({ opacity }) => (
  <div
    style={{
      opacity,
      width: 720,
      margin: "0 auto",
      borderRadius: 10,
      overflow: "hidden",
      border: `1px solid ${BORDER}`,
      boxShadow: "0 16px 48px rgba(0,0,0,0.5)",
      background: "#1a1a2e",
    }}
  >
    {/* n8n top bar */}
    <div
      style={{
        background: "#16213e",
        height: 32,
        display: "flex",
        alignItems: "center",
        padding: "0 12px",
        gap: 8,
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: 5,
          background: "#ff5f56",
        }}
      />
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: 5,
          background: "#ffbd2e",
        }}
      />
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: 5,
          background: "#27c93f",
        }}
      />
      <span
        style={{
          flex: 1,
          textAlign: "center",
          color: DIM,
          fontSize: 11,
          fontFamily: "sans-serif",
        }}
      >
        n8n — AI Agent with Tools
      </span>
    </div>
    {/* Canvas with nodes */}
    <div
      style={{
        height: 220,
        background:
          "radial-gradient(circle at 50% 50%, #1a1a2e 0%, #0f0f23 100%)",
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 40,
      }}
    >
      {/* Grid dots */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `radial-gradient(circle, ${BORDER}44 1px, transparent 1px)`,
          backgroundSize: "20px 20px",
        }}
      />
      {/* Webhook node */}
      <div style={{ zIndex: 1, display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            background: "#2d4a22",
            border: "2px solid #4ade80",
            borderRadius: 8,
            padding: "10px 14px",
            textAlign: "center",
            fontFamily: "sans-serif",
          }}
        >
          <div style={{ fontSize: 18, marginBottom: 2 }}>🔗</div>
          <div style={{ fontSize: 10, color: TEXT, fontWeight: 600 }}>
            Webhook
          </div>
          <div style={{ fontSize: 8, color: DIM }}>Trigger</div>
        </div>
      </div>
      {/* Arrow */}
      <div
        style={{
          zIndex: 1,
          color: ACCENT,
          fontSize: 20,
          letterSpacing: -4,
        }}
      >
        ——→
      </div>
      {/* Trusera Dashboard node */}
      <div style={{ zIndex: 1 }}>
        <div
          style={{
            background: "#1e293b",
            border: `2px solid ${ACCENT}`,
            borderRadius: 8,
            padding: "10px 14px",
            textAlign: "center",
            fontFamily: "sans-serif",
            boxShadow: `0 0 20px ${ACCENT}33`,
          }}
        >
          <TruseraLogo size={24} />
          <div
            style={{
              fontSize: 10,
              color: TEXT,
              fontWeight: 600,
              marginTop: 2,
            }}
          >
            Trusera Dashboard
          </div>
          <div style={{ fontSize: 8, color: ACCENT }}>AI Security Scan</div>
        </div>
      </div>
      {/* Arrow */}
      <div
        style={{
          zIndex: 1,
          color: ACCENT,
          fontSize: 20,
          letterSpacing: -4,
        }}
      >
        ——→
      </div>
      {/* Respond node */}
      <div style={{ zIndex: 1 }}>
        <div
          style={{
            background: "#3b2e1a",
            border: "2px solid #d29922",
            borderRadius: 8,
            padding: "10px 14px",
            textAlign: "center",
            fontFamily: "sans-serif",
          }}
        >
          <div style={{ fontSize: 18, marginBottom: 2 }}>📄</div>
          <div style={{ fontSize: 10, color: TEXT, fontWeight: 600 }}>
            Respond
          </div>
          <div style={{ fontSize: 8, color: DIM }}>HTML</div>
        </div>
      </div>
    </div>
  </div>
);

// ─── Main component ─────────────────────────────────────────────
export const N8nDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ════════════════════════════════════════════════════════════════
  // Scene timing (450 frames = 15 seconds at 30fps)
  // ════════════════════════════════════════════════════════════════
  // 0-60    : Logo + title card
  // 60-150  : Terminal install animation
  // 150-240 : n8n editor with 2-node workflow
  // 240-360 : Dashboard with stat cards + findings table
  // 360-420 : Zoom on remediation card
  // 420-450 : CTA

  // ── Scene 1: Logo + Title (0-60) ──
  const logoScale = spring({ frame, fps, from: 0.5, to: 1, durationInFrames: 20 });
  const logoOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleOpacity = interpolate(frame, [15, 30], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subtitleOpacity = interpolate(frame, [25, 40], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scene1Out = interpolate(frame, [50, 60], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ── Scene 2: Terminal install (60-150) ──
  const scene2In = interpolate(frame, [60, 75], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scene2Out = interpolate(frame, [140, 150], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cmd = "npm install n8n-nodes-trusera";
  const typedCmd = typeText(cmd, frame, 80, 0.8);
  const cmdDone = frame >= 80 + cmd.length / 0.8;
  const installSuccess = showAfter(frame, 120);

  // ── Scene 3: n8n Editor (150-240) ──
  const scene3In = interpolate(frame, [150, 165], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scene3Out = interpolate(frame, [230, 240], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ── Scene 4: Dashboard (240-360) ──
  const scene4In = interpolate(frame, [240, 255], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scene4Out = interpolate(frame, [350, 360], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const statDelay = [250, 256, 262, 268];

  // ── Scene 5: Remediation card zoom (360-420) ──
  const scene5In = interpolate(frame, [360, 375], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scene5Out = interpolate(frame, [410, 420], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ── Scene 6: CTA (420-450) ──
  const ctaOpacity = interpolate(frame, [420, 435], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "#010409",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
        overflow: "hidden",
      }}
    >
      {/* ═══ Scene 1: Logo + Title ═══ */}
      {frame < 65 && (
        <div
          style={{
            opacity: scene1Out,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div
            style={{
              opacity: logoOpacity,
              transform: `scale(${logoScale})`,
            }}
          >
            <TruseraLogo size={80} />
          </div>
          <div
            style={{
              opacity: titleOpacity,
              fontSize: 32,
              fontWeight: 700,
              color: TEXT,
            }}
          >
            <span style={{ color: ACCENT }}>AI-BOM</span> for n8n
          </div>
          <div
            style={{
              opacity: subtitleOpacity,
              fontSize: 14,
              color: DIM,
              maxWidth: 400,
              textAlign: "center",
            }}
          >
            Scan every workflow for AI security risks — directly inside n8n
          </div>
        </div>
      )}

      {/* ═══ Scene 2: Terminal Install ═══ */}
      {frame >= 60 && frame < 155 && (
        <div style={{ opacity: Math.min(scene2In, scene2Out) }}>
          <div
            style={{
              width: 600,
              borderRadius: 10,
              overflow: "hidden",
              border: `1px solid ${BORDER}`,
              boxShadow: "0 16px 48px rgba(0,0,0,0.6)",
            }}
          >
            <div
              style={{
                background: CARD_BG,
                height: 32,
                display: "flex",
                alignItems: "center",
                padding: "0 12px",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: "#ff5f56",
                }}
              />
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: "#ffbd2e",
                }}
              />
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: "#27c93f",
                }}
              />
              <span
                style={{
                  flex: 1,
                  textAlign: "center",
                  color: DIM,
                  fontSize: 11,
                  fontFamily: "monospace",
                }}
              >
                Terminal
              </span>
            </div>
            <div
              style={{
                background: BG,
                padding: "16px 18px",
                fontFamily:
                  "'SF Mono', 'Fira Code', 'Cascadia Code', monospace",
                fontSize: 14,
                lineHeight: 1.8,
                color: TEXT,
                minHeight: 120,
              }}
            >
              <div>
                <span style={{ color: GREEN }}>$</span> {typedCmd}
                {!cmdDone && <Cursor />}
              </div>
              {installSuccess && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ color: DIM }}>
                    added 1 package in 2.3s
                  </div>
                  <div style={{ color: GREEN, marginTop: 4 }}>
                    ✓ n8n-nodes-trusera@0.4.0 installed
                  </div>
                  <div style={{ color: DIM, marginTop: 8 }}>
                    Restart n8n to load the community node
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ Scene 3: n8n Workflow Editor ═══ */}
      {frame >= 150 && frame < 245 && (
        <div
          style={{
            opacity: Math.min(scene3In, scene3Out),
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 13,
              color: DIM,
              fontWeight: 600,
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            2-Node Workflow Setup
          </div>
          <N8nEditorMockup opacity={1} />
        </div>
      )}

      {/* ═══ Scene 4: Dashboard Results ═══ */}
      {frame >= 240 && frame < 365 && (
        <div
          style={{
            opacity: Math.min(scene4In, scene4Out),
            width: 740,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <TruseraLogo size={22} />
              <span style={{ fontSize: 16, fontWeight: 600, color: TEXT }}>
                <span style={{ color: ACCENT }}>Trusera</span> AI-BOM Dashboard
              </span>
            </div>
            <span style={{ fontSize: 11, color: DIM }}>v0.4.0</span>
          </div>

          {/* Stat cards */}
          <div style={{ display: "flex", gap: 10 }}>
            {[
              { value: "12", label: "Components", color: ACCENT },
              { value: "5", label: "Workflows Scanned", color: PURPLE },
              { value: "60", label: "Highest Risk Score", color: RED },
              { value: "0.42s", label: "Scan Duration", color: DIM },
            ].map((s, i) => (
              <StatCard
                key={i}
                {...s}
                opacity={interpolate(
                  frame,
                  [statDelay[i], statDelay[i] + 10],
                  [0, 1],
                  { extrapolateRight: "clamp" }
                )}
              />
            ))}
          </div>

          {/* Findings table */}
          <div
            style={{
              background: CARD_BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              padding: "10px 14px",
              opacity: interpolate(frame, [275, 285], [0, 1], {
                extrapolateRight: "clamp",
              }),
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: DIM,
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                marginBottom: 8,
              }}
            >
              Findings
            </div>
            {/* Table header */}
            <div
              style={{
                display: "flex",
                fontSize: 10,
                color: DIM,
                borderBottom: `1px solid ${BORDER}`,
                paddingBottom: 4,
                marginBottom: 4,
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}
            >
              <span style={{ width: 160 }}>Name</span>
              <span style={{ width: 100 }}>Type</span>
              <span style={{ width: 100 }}>Workflow</span>
              <span style={{ width: 60, textAlign: "center" }}>Severity</span>
              <span style={{ width: 50, textAlign: "center" }}>Score</span>
              <span style={{ flex: 1 }}>Flags</span>
            </div>
            {/* Rows */}
            {findings.map((f, i) => {
              const rowStart = 285 + i * 10;
              if (!showAfter(frame, rowStart)) return null;
              const rowOpacity = interpolate(
                frame,
                [rowStart, rowStart + 8],
                [0, 1],
                { extrapolateRight: "clamp" }
              );
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    fontSize: 11,
                    padding: "3px 0",
                    opacity: rowOpacity,
                    borderBottom:
                      i < findings.length - 1
                        ? `1px solid ${BORDER}44`
                        : "none",
                    alignItems: "center",
                  }}
                >
                  <span style={{ width: 160, color: TEXT, fontWeight: 600 }}>
                    {f.name}
                  </span>
                  <span style={{ width: 100, color: DIM }}>
                    {f.type.replace(/_/g, " ")}
                  </span>
                  <span style={{ width: 100, color: DIM, fontSize: 10 }}>
                    {f.workflow}
                  </span>
                  <span style={{ width: 60, textAlign: "center" }}>
                    <Badge sev={f.sev} small />
                  </span>
                  <span
                    style={{
                      width: 50,
                      textAlign: "center",
                      color: sevColor(f.sev),
                      fontWeight: 700,
                    }}
                  >
                    {f.score}
                  </span>
                  <span style={{ flex: 1, color: DIM, fontSize: 10 }}>
                    {f.flags.join(", ")}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ Scene 5: Remediation Card Zoom ═══ */}
      {frame >= 360 && frame < 425 && (
        <div
          style={{
            opacity: Math.min(scene5In, scene5Out),
            width: 620,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div
            style={{
              fontSize: 13,
              color: DIM,
              fontWeight: 600,
              letterSpacing: 1,
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            Actionable Remediation
          </div>
          {remediationCards.map((card, i) => {
            const cardStart = 370 + i * 20;
            const cardOpacity = interpolate(
              frame,
              [cardStart, cardStart + 12],
              [0, 1],
              { extrapolateRight: "clamp" }
            );
            return (
              <div
                key={i}
                style={{
                  opacity: cardOpacity,
                  borderLeft: `4px solid ${sevColor(card.sev)}`,
                  background: BG,
                  borderRadius: "0 8px 8px 0",
                  padding: "12px 16px",
                  border: `1px solid ${BORDER}`,
                  borderLeftWidth: 4,
                  borderLeftColor: sevColor(card.sev),
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <code
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: TEXT,
                      fontFamily: "monospace",
                    }}
                  >
                    {card.flag}
                  </code>
                  <Badge sev={card.sev} />
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: 10,
                      fontWeight: 600,
                      background: `${PURPLE}cc`,
                      color: "#fff",
                      padding: "1px 6px",
                      borderRadius: 3,
                    }}
                  >
                    {card.owasp}
                  </span>
                </div>
                <div
                  style={{ fontSize: 11, color: DIM, lineHeight: 1.5 }}
                >
                  {card.desc}
                </div>
                <div style={{ marginTop: 6 }}>
                  <div
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      color: TEXT,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 2,
                    }}
                  >
                    Remediation
                  </div>
                  <div
                    style={{ fontSize: 11, color: GREEN, lineHeight: 1.5 }}
                  >
                    {card.fix}
                  </div>
                </div>
                <div style={{ marginTop: 4 }}>
                  <div
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      color: TEXT,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 2,
                    }}
                  >
                    Guardrail
                  </div>
                  <div
                    style={{ fontSize: 11, color: ACCENT, lineHeight: 1.5 }}
                  >
                    {card.guardrail}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══ Scene 6: CTA ═══ */}
      {frame >= 420 && (
        <div
          style={{
            opacity: ctaOpacity,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          <TruseraLogo size={48} />
          <div style={{ fontSize: 22, fontWeight: 700, color: TEXT }}>
            Install from npm
          </div>
          <div
            style={{
              background: CARD_BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              padding: "10px 24px",
              fontFamily: "monospace",
              fontSize: 16,
              color: ACCENT,
            }}
          >
            npm install n8n-nodes-trusera
          </div>
          <div style={{ fontSize: 13, color: DIM, marginTop: 4 }}>
            <span style={{ color: TEAL }}>github.com/trusera/ai-bom</span>
            <span style={{ color: DIM }}> &nbsp;|&nbsp; </span>
            <span style={{ color: ACCENT }}>trusera.dev</span>
          </div>
        </div>
      )}
    </div>
  );
};
