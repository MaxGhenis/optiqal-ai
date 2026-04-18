import { ImageResponse } from "next/og";

export const runtime = "edge";

export const size = {
  width: 32,
  height: 32,
};

export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#f6f1e8",
        }}
      >
        <svg
          width="28"
          height="28"
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
            fill="#fcfaf5"
            stroke="#2d7168"
            strokeOpacity="0.2"
            strokeWidth="1.4"
          />
          <circle
            cx="21"
            cy="21"
            r="9.5"
            stroke="#2d7168"
            strokeWidth="2.6"
            fill="none"
          />
          <path d="M27.8 27.8L34.6 34.6" stroke="#d97a5e" strokeWidth="2.8" strokeLinecap="round" />
          <rect x="15.5" y="22" width="2.6" height="7.5" rx="1.3" fill="#74d0ca" />
          <rect x="20.6" y="18.5" width="2.6" height="10" rx="1.3" fill="#2d7168" fillOpacity="0.8" />
          <rect x="25.7" y="15" width="2.6" height="13.5" rx="1.3" fill="#d97a5e" fillOpacity="0.82" />
          <circle cx="21" cy="21" r="1.7" fill="#1f2729" fillOpacity="0.18" />
        </svg>
      </div>
    ),
    size
  );
}
