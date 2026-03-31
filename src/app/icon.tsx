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
            cx="22"
            cy="22"
            r="10"
            stroke="#2d7168"
            strokeWidth="2.6"
            fill="none"
          />
          <path d="M28.5 28.5L35 35" stroke="#d97a5e" strokeWidth="2.8" strokeLinecap="round" />
          <rect x="15" y="24" width="3.5" height="6.5" rx="1.75" fill="#74d0ca" />
          <rect x="21" y="20.5" width="3.5" height="10" rx="1.75" fill="#2d7168" fillOpacity="0.8" />
          <rect x="27" y="17" width="3.5" height="13.5" rx="1.75" fill="#d97a5e" fillOpacity="0.82" />
          <path
            d="M12.5 29.5C16.1 27.6 19.6 24.8 23.1 21.2C25.5 18.7 28.1 16.9 31 15.8"
            stroke="#1f2729"
            strokeOpacity="0.18"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </div>
    ),
    size
  );
}
