import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "Optiqal — Understand Your Healthspan";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
        }}
      >
        {/* Gradient orbs */}
        <div
          style={{
            position: "absolute",
            top: "10%",
            left: "10%",
            width: 300,
            height: 300,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(20, 184, 166, 0.3) 0%, transparent 70%)",
            filter: "blur(40px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "10%",
            right: "15%",
            width: 250,
            height: 250,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(244, 114, 182, 0.2) 0%, transparent 70%)",
            filter: "blur(40px)",
          }}
        />

        {/* Logo and brand */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 40,
          }}
        >
          {/* Pulse icon */}
          <svg
            width="64"
            height="64"
            viewBox="0 0 32 32"
            fill="none"
            style={{ color: "#14b8a6" }}
          >
            <circle
              cx="16"
              cy="16"
              r="14"
              stroke="currentColor"
              strokeWidth="2.5"
              fill="none"
            />
            <path
              d="M6 16 L11 16 L13 10 L16 22 L19 14 L21 16 L26 16"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
          <span
            style={{
              fontSize: 48,
              fontWeight: 600,
              color: "white",
              letterSpacing: "-0.02em",
            }}
          >
            optiqal
          </span>
        </div>

        {/* Main headline */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 500,
            textAlign: "center",
            lineHeight: 1.1,
            marginBottom: 24,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <span style={{ color: "white" }}>Understand your</span>
          <span
            style={{
              background: "linear-gradient(90deg, #14b8a6 0%, #06b6d4 50%, #f472b6 100%)",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            healthspan
          </span>
        </div>

        {/* Subheadline */}
        <p
          style={{
            fontSize: 28,
            color: "#94a3b8",
            textAlign: "center",
            maxWidth: 800,
            lineHeight: 1.4,
          }}
        >
          Explore how lifestyle factors affect life expectancy
          and quality of life, based on published research.
        </p>

        {/* Bottom tag */}
        <div
          style={{
            position: "absolute",
            bottom: 40,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 20px",
            borderRadius: 999,
            border: "1px solid rgba(20, 184, 166, 0.3)",
            background: "rgba(20, 184, 166, 0.1)",
          }}
        >
          <span style={{ fontSize: 18, color: "#14b8a6" }}>
            AI-powered QALY estimation
          </span>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
