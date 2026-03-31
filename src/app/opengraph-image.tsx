import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "Optiqal — Rank Your Health Interventions";
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
            gap: 18,
            marginBottom: 40,
          }}
        >
          <svg
            width="78"
            height="78"
            viewBox="0 0 48 48"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect
              x="4"
              y="4"
              width="40"
              height="40"
              rx="13"
              fill="rgba(246, 241, 232, 0.08)"
              stroke="rgba(86, 196, 191, 0.24)"
              strokeWidth="1.4"
            />
            <circle cx="22" cy="22" r="10" stroke="#56c4bf" strokeWidth="2.5" />
            <path d="M28.5 28.5L35 35" stroke="#e08a73" strokeWidth="2.8" strokeLinecap="round" />
            <rect x="15" y="24" width="3.5" height="6.5" rx="1.75" fill="#7dd8d2" />
            <rect x="21" y="20.5" width="3.5" height="10" rx="1.75" fill="#56c4bf" />
            <rect x="27" y="17" width="3.5" height="13.5" rx="1.75" fill="#e08a73" fillOpacity="0.92" />
            <path
              d="M12.5 29.5C16.1 27.6 19.6 24.8 23.1 21.2C25.5 18.7 28.1 16.9 31 15.8"
              stroke="rgba(248, 250, 252, 0.18)"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                fontSize: 50,
                fontWeight: 600,
                color: "white",
                letterSpacing: "-0.05em",
              }}
            >
              Opti<span style={{ color: "#56c4bf" }}>q</span>al
            </div>
            <div
              style={{
                marginTop: 4,
                fontSize: 14,
                letterSpacing: "0.34em",
                textTransform: "uppercase",
                color: "#94a3b8",
              }}
            >
              Decision engine
            </div>
          </div>
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
          <span style={{ color: "white" }}>Rank your next</span>
          <span
            style={{
              background: "linear-gradient(90deg, #14b8a6 0%, #06b6d4 50%, #f472b6 100%)",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            health move
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
          Compare sleep, exercise, lipids, supplements, and more on one
          evidence-aware scale.
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
            Personalized intervention ranking
          </span>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
