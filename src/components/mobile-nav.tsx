"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="p-2 text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Toggle menu"
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 glass border-t border-border/50 animate-slide-down">
          <nav className="flex flex-col p-4 gap-2">
            <Link
              href="#how-it-works"
              onClick={() => setOpen(false)}
              className="px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded-lg transition-colors"
            >
              How it works
            </Link>
            <Link
              href="/about"
              onClick={() => setOpen(false)}
              className="px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded-lg transition-colors"
            >
              About
            </Link>
            <Link
              href="/faq"
              onClick={() => setOpen(false)}
              className="px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded-lg transition-colors"
            >
              FAQ
            </Link>
            <div className="pt-2">
              <Button
                className="w-full btn-glow bg-primary text-primary-foreground hover:bg-primary/90"
                asChild
              >
                <Link href="/predict" onClick={() => setOpen(false)}>
                  Try it free
                  <Sparkles className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
