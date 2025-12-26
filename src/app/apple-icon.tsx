import { ImageResponse } from "next/og";

export const runtime = "edge";

export const size = {
  width: 180,
  height: 180,
};

export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0f172a",
          borderRadius: "22%",
        }}
      >
        <svg
          width="140"
          height="140"
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Outer circle (the O) */}
          <circle
            cx="16"
            cy="16"
            r="14"
            stroke="#14b8a6"
            strokeWidth="3"
            fill="none"
          />
          {/* Pulse/heartbeat line through the center */}
          <path
            d="M4 16 L10 16 L12 12 L14 20 L16 10 L18 22 L20 14 L22 16 L28 16"
            stroke="#14b8a6"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      </div>
    ),
    {
      ...size,
    }
  );
}
