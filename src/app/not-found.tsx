import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, ArrowRight, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen mesh-gradient relative overflow-hidden flex items-center justify-center px-6">
      {/* Noise texture */}
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      <Card className="max-w-md w-full mesh-gradient-card border-border/50 card-highlight">
        <CardContent className="p-8 text-center space-y-6">
          {/* Icon */}
          <div className="relative w-16 h-16 mx-auto">
            <div className="absolute inset-0 rounded-full bg-primary/20 blur-xl animate-pulse-glow" />
            <div className="relative w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-transparent border border-primary/30 flex items-center justify-center">
              <Activity className="h-8 w-8 text-primary" />
            </div>
          </div>

          {/* Message */}
          <div className="space-y-2">
            <h1 className="font-serif text-3xl font-medium">Page not found</h1>
            <p className="text-muted-foreground">
              The page you're looking for doesn't exist. Explore how lifestyle
              factors affect your healthspan instead.
            </p>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Button
              variant="outline"
              className="flex-1 border-border/50 hover:border-primary/50 hover:bg-primary/5"
              asChild
            >
              <Link href="/">
                <Home className="mr-2 h-4 w-4" />
                Home
              </Link>
            </Button>
            <Button
              className="flex-1 btn-glow bg-primary text-primary-foreground hover:bg-primary/90"
              asChild
            >
              <Link href="/predict">
                Explore
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
