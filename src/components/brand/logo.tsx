import { cn } from "@/lib/utils";

type LogoMarkProps = {
  className?: string;
};

type LogoWordmarkProps = {
  className?: string;
  nameClassName?: string;
  descriptorClassName?: string;
  descriptor?: string;
  showDescriptor?: boolean;
  size?: "sm" | "md" | "lg";
};

type LogoLockupProps = LogoWordmarkProps & {
  markClassName?: string;
};

const SIZE_STYLES = {
  sm: {
    mark: "h-9 w-9",
    name: "text-[0.98rem]",
    q: "w-[0.68em]",
    qTail: "h-[0.24em] w-[0.38em]",
    descriptor: "text-[0.62rem]",
    gap: "gap-2.5",
  },
  md: {
    mark: "h-10 w-10",
    name: "text-[1.08rem]",
    q: "w-[0.72em]",
    qTail: "h-[0.26em] w-[0.42em]",
    descriptor: "text-[0.66rem]",
    gap: "gap-3",
  },
  lg: {
    mark: "h-14 w-14",
    name: "text-[1.68rem]",
    q: "w-[0.8em]",
    qTail: "h-[0.32em] w-[0.5em]",
    descriptor: "text-[0.72rem]",
    gap: "gap-3.5",
  },
} as const;

export function LogoMark({ className }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("block", className)}
      aria-hidden="true"
    >
      <rect
        x="4"
        y="4"
        width="40"
        height="40"
        rx="13"
        fill="hsl(var(--surface-panel))"
        stroke="hsl(var(--brand) / 0.18)"
        strokeWidth="1.4"
      />
      <circle
        cx="21"
        cy="21"
        r="9.5"
        stroke="hsl(var(--brand))"
        strokeWidth="2.4"
      />
      <path
        d="M27.8 27.8L34.6 34.6"
        stroke="hsl(var(--accent))"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <rect
        x="15.5"
        y="22"
        width="2.6"
        height="7.5"
        rx="1.3"
        fill="hsl(var(--brand) / 0.55)"
      />
      <rect
        x="20.6"
        y="18.5"
        width="2.6"
        height="10"
        rx="1.3"
        fill="hsl(var(--brand) / 0.78)"
      />
      <rect
        x="25.7"
        y="15"
        width="2.6"
        height="13.5"
        rx="1.3"
        fill="hsl(var(--accent) / 0.78)"
      />
      <circle cx="21" cy="21" r="1.7" fill="hsl(var(--foreground) / 0.12)" />
    </svg>
  );
}

export function LogoWordmark({
  className,
  nameClassName,
  descriptorClassName,
  descriptor = "Decision engine",
  showDescriptor = true,
  size = "md",
}: LogoWordmarkProps) {
  const styles = SIZE_STYLES[size];

  return (
    <div className={cn("min-w-0 leading-none", className)}>
      <div
        className={cn(
          "flex items-center gap-[0.02em] font-sans font-semibold uppercase tracking-[0.17em] text-foreground",
          styles.name,
          nameClassName
        )}
      >
        <span>OPTI</span>
        <span className={cn("relative inline-flex justify-center", styles.q)}>
          <span>Q</span>
          <span
            className={cn(
              "absolute left-[62%] top-[68%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[hsl(var(--accent)/0.75)] rotate-[46deg]",
              styles.qTail
            )}
          />
        </span>
        <span>AL</span>
      </div>
      {showDescriptor ? (
        <div
          className={cn(
            "mt-1 font-mono uppercase tracking-[0.24em] text-muted-foreground",
            styles.descriptor,
            descriptorClassName
          )}
        >
          {descriptor}
        </div>
      ) : null}
    </div>
  );
}

export function LogoLockup({
  className,
  markClassName,
  size = "md",
  ...wordmarkProps
}: LogoLockupProps) {
  const styles = SIZE_STYLES[size];

  return (
    <div className={cn("flex items-center", styles.gap, className)}>
      <LogoMark className={cn(styles.mark, markClassName)} />
      <LogoWordmark size={size} {...wordmarkProps} />
    </div>
  );
}
