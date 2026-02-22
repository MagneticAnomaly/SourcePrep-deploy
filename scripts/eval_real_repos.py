#!/usr/bin/env python3
"""Evaluate CoDRAG retrieval quality on real-world repositories.

Tests all 3 embedding tiers against ground-truth queries for real repos:
- mini-redis (Rust, tokio): TCP server, commands, pub/sub, key expiry
- click (Python, pallets): CLI framework, decorators, parameter types
- TEST (Next.js/React): Marketing website with components and hooks

Usage:
    python scripts/eval_real_repos.py                    # All repos, ONNX only
    python scripts/eval_real_repos.py --tiers all        # All repos, all tiers
    python scripts/eval_real_repos.py --repos mini-redis  # Single repo
    python scripts/eval_real_repos.py --verbose          # Show all misses
"""

import argparse
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from codrag.core import CodeIndex, NativeEmbedder
from codrag.core.embedder import Embedder, EmbeddingResult, OllamaEmbedder


# ---------------------------------------------------------------------------
# Ground truth for each repo
# ---------------------------------------------------------------------------

REPOS: Dict[str, Dict[str, Any]] = {
    "mini-redis": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "mini-redis-rust",
        "language": "Rust",
        "queries": [
            {"query": "shared database state HashMap key value storage", "expected_file": "src/db.rs"},
            {"query": "key expiration background purge task", "expected_file": "src/db.rs"},
            {"query": "TCP connection read write frames buffer", "expected_file": "src/connection.rs"},
            {"query": "Redis protocol frame parsing", "expected_file": "src/frame.rs"},
            {"query": "server listener accept TCP connections", "expected_file": "src/server.rs"},
            {"query": "graceful shutdown signal notification", "expected_file": "src/shutdown.rs"},
            {"query": "GET command retrieve value by key", "expected_file": "src/cmd/get.rs"},
            {"query": "SET command store key value with expiry", "expected_file": "src/cmd/set.rs"},
            {"query": "PUBLISH command send message to channel", "expected_file": "src/cmd/publish.rs"},
            {"query": "SUBSCRIBE command listen for channel messages", "expected_file": "src/cmd/subscribe.rs"},
            {"query": "parse command from frame into Command enum", "expected_file": "src/cmd/mod.rs"},
            {"query": "PING command health check", "expected_file": "src/cmd/ping.rs"},
            {"query": "blocking client synchronous redis operations", "expected_file": "src/clients/blocking_client.rs"},
            {"query": "async client send commands over connection", "expected_file": "src/clients/client.rs"},
            {"query": "command line interface CLI arguments server port", "expected_file": "src/bin/server.rs"},
            {"query": "parse cursor extract data from bytes", "expected_file": "src/parse.rs"},
        ],
    },
    "click": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "click-python",
        "language": "Python",
        "queries": [
            {"query": "Command class invoke callback with parameters", "expected_file": "src/click/core.py"},
            {"query": "Group class manage subcommands", "expected_file": "src/click/core.py"},
            {"query": "Context object pass data between commands", "expected_file": "src/click/core.py"},
            {"query": "click.command decorator create CLI command", "expected_file": "src/click/decorators.py"},
            {"query": "click.option decorator add command line option", "expected_file": "src/click/decorators.py"},
            {"query": "pass_context decorator inject context", "expected_file": "src/click/decorators.py"},
            {"query": "ParamType validate and convert parameter values", "expected_file": "src/click/types.py"},
            {"query": "Choice type restrict to set of values", "expected_file": "src/click/types.py"},
            {"query": "File type open file path parameter", "expected_file": "src/click/types.py"},
            {"query": "CliRunner test CLI commands programmatically", "expected_file": "src/click/testing.py"},
            {"query": "format help text and usage message", "expected_file": "src/click/formatting.py"},
            {"query": "shell tab completion", "expected_file": "src/click/shell_completion.py"},
            {"query": "ClickException custom error handling", "expected_file": "src/click/exceptions.py"},
            {"query": "option parser split arguments", "expected_file": "src/click/parser.py"},
            {"query": "progress bar terminal UI", "expected_file": "src/click/termui.py"},
            {"query": "echo print output to terminal", "expected_file": "src/click/utils.py"},
        ],
    },
    "spark-java": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "spark-java",
        "language": "Java",
        "queries": [
            {"query": "HTTP request object get headers cookies query params", "expected_file": "src/main/java/spark/Request.java"},
            {"query": "HTTP response set status code body content type", "expected_file": "src/main/java/spark/Response.java"},
            {"query": "Route interface handle request response callback", "expected_file": "src/main/java/spark/Route.java"},
            {"query": "Filter interface before after middleware", "expected_file": "src/main/java/spark/Filter.java"},
            {"query": "Service class configure server port SSL routes", "expected_file": "src/main/java/spark/Service.java"},
            {"query": "Spark static methods get post put delete routing", "expected_file": "src/main/java/spark/Spark.java"},
            {"query": "session management store retrieve attributes", "expected_file": "src/main/java/spark/Session.java"},
            {"query": "route matching find handler for HTTP method and path", "expected_file": "src/main/java/spark/route/Routes.java"},
            {"query": "embedded Jetty server start stop listen on port", "expected_file": "src/main/java/spark/embeddedserver/jetty/EmbeddedJettyServer.java"},
            {"query": "SSL keystore truststore certificate configuration", "expected_file": "src/main/java/spark/ssl/SslStores.java"},
            {"query": "static files serve from classpath or external folder", "expected_file": "src/main/java/spark/staticfiles/StaticFilesConfiguration.java"},
            {"query": "exception handler map exception class to handler", "expected_file": "src/main/java/spark/ExceptionMapper.java"},
            {"query": "redirect HTTP status codes 301 302 temporary permanent", "expected_file": "src/main/java/spark/Redirect.java"},
            {"query": "query string parameter parsing nested map", "expected_file": "src/main/java/spark/QueryParamsMap.java"},
            {"query": "template engine render ModelAndView", "expected_file": "src/main/java/spark/TemplateEngine.java"},
            {"query": "response body serializer chain write output stream", "expected_file": "src/main/java/spark/serialization/Serializer.java"},
        ],
    },
    "chi": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "chi-go",
        "language": "Go",
        "queries": [
            {"query": "mux router register HTTP handler route", "expected_file": "mux.go"},
            {"query": "context request URL params route values", "expected_file": "context.go"},
            {"query": "URL path pattern matching segments wildcards", "expected_file": "pattern.go"},
            {"query": "radix tree node route lookup insert", "expected_file": "tree.go"},
            {"query": "middleware chain wrap handler stack compose", "expected_file": "chain.go"},
            {"query": "compress gzip deflate response middleware", "expected_file": "middleware/compress.go"},
            {"query": "rate limiter throttle requests per second", "expected_file": "middleware/throttle.go"},
            {"query": "request logger format print middleware", "expected_file": "middleware/logger.go"},
            {"query": "recover panic 500 error middleware", "expected_file": "middleware/recoverer.go"},
            {"query": "real client IP X-Forwarded-For address", "expected_file": "middleware/realip.go"},
            {"query": "basic auth username password HTTP header", "expected_file": "middleware/basic_auth.go"},
            {"query": "request ID unique identifier per request", "expected_file": "middleware/request_id.go"},
        ],
    },
    "gin": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "gin-go",
        "language": "Go",
        "queries": [
            {"query": "Engine router new instance HTTP server create", "expected_file": "gin.go"},
            {"query": "Context request response body JSON params bind", "expected_file": "context.go"},
            {"query": "router group add routes path prefix", "expected_file": "routergroup.go"},
            {"query": "basic auth middleware credentials check", "expected_file": "auth.go"},
            {"query": "logger middleware format request response log", "expected_file": "logger.go"},
            {"query": "recovery middleware panic recover internal error", "expected_file": "recovery.go"},
            {"query": "radix tree pattern route node matching algorithm", "expected_file": "tree.go"},
            {"query": "response writer status code header write body", "expected_file": "response_writer.go"},
            {"query": "render JSON HTML template XML response", "expected_file": "render/render.go"},
            {"query": "error collect meta type message", "expected_file": "errors.go"},
            {"query": "debug mode print registered routes list", "expected_file": "debug.go"},
        ],
    },
    "cobra": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "cobra-go",
        "language": "Go",
        "queries": [
            {"query": "Command struct run execute callback function", "expected_file": "command.go"},
            {"query": "argument validation positional args check", "expected_file": "args.go"},
            {"query": "shell completion suggest subcommands flags", "expected_file": "completions.go"},
            {"query": "bash completion script generate", "expected_file": "bash_completions.go"},
            {"query": "flag groups required mutually exclusive", "expected_file": "flag_groups.go"},
            {"query": "PowerShell completion script generate", "expected_file": "powershell_completions.go"},
            {"query": "zsh completion script generate", "expected_file": "zsh_completions.go"},
            {"query": "active help completion message hint", "expected_file": "active_help.go"},
            {"query": "generate markdown documentation docs", "expected_file": "doc/md_docs.go"},
            {"query": "generate man page manual documentation", "expected_file": "doc/man_docs.go"},
        ],
    },
    "got": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "got-typescript",
        "language": "TypeScript",
        "queries": [
            {"query": "request options URL method headers normalize", "expected_file": "source/core/options.ts"},
            {"query": "error types HTTPError CancelError RequestError", "expected_file": "source/core/errors.ts"},
            {"query": "retry delay calculate exponential backoff", "expected_file": "source/core/calculate-retry-delay.ts"},
            {"query": "response object body status code headers", "expected_file": "source/core/response.ts"},
            {"query": "timeout connect send response milliseconds abort", "expected_file": "source/core/timed-out.ts"},
            {"query": "promise normalize request send receive", "expected_file": "source/as-promise/index.ts"},
            {"query": "create instance extend got defaults merge", "expected_file": "source/create.ts"},
            {"query": "main entry point exports got library", "expected_file": "source/index.ts"},
            {"query": "body size calculate content-length stream", "expected_file": "source/core/utils/get-body-size.ts"},
            {"query": "timer event timing phases track", "expected_file": "source/core/utils/timer.ts"},
        ],
    },
    "hanami": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "hanami-ruby",
        "language": "Ruby",
        "queries": [
            {"query": "router HTTP routes define endpoint path", "expected_file": "lib/hanami/router.rb"},
            {"query": "body parser JSON parse request body middleware", "expected_file": "lib/hanami/middleware/body_parser/json_parser.rb"},
            {"query": "middleware stack wrap Rack application", "expected_file": "lib/hanami/middleware/app.rb"},
            {"query": "trie data structure path route lookup", "expected_file": "lib/hanami/middleware/trie.rb"},
            {"query": "router not found exception error class", "expected_file": "lib/hanami/router/errors.rb"},
            {"query": "route leaf node endpoint resolve", "expected_file": "lib/hanami/router/leaf.rb"},
            {"query": "block DSL scope router define routes", "expected_file": "lib/hanami/router/block.rb"},
            {"query": "globbed wildcard path route matching", "expected_file": "lib/hanami/router/globbed_path.rb"},
            {"query": "middleware node trie insert path", "expected_file": "lib/hanami/middleware/node.rb"},
        ],
    },
    "slim": {
        "path": PROJECT_ROOT / "tests" / "eval" / "real_repos" / "slim-php",
        "language": "PHP",
        "queries": [
            {"query": "App class create run PSR-7 application", "expected_file": "Slim/App.php"},
            {"query": "callable resolver invoke handler PSR", "expected_file": "Slim/CallableResolver.php"},
            {"query": "error handler exception render response", "expected_file": "Slim/Error/AbstractErrorRenderer.php"},
            {"query": "HTTP exception 404 not found 403 forbidden", "expected_file": "Slim/Exception/HttpException.php"},
            {"query": "factory create Slim application builder", "expected_file": "Slim/Factory/AppFactory.php"},
            {"query": "JSON error renderer exception output", "expected_file": "Slim/Error/Renderers/JsonErrorRenderer.php"},
            {"query": "router dispatch resolve route handler", "expected_file": "Slim/Routing/RouteCollector.php"},
            {"query": "middleware runner execute stack PSR-15", "expected_file": "Slim/MiddlewareDispatcher.php"},
        ],
    },
    "test-nextjs": {
        "path": PROJECT_ROOT / "TEST",
        "language": "TypeScript/React",
        "queries": [
            {"query": "hero section component with animation", "expected_file": "src/components/EnhancedHero.tsx"},
            {"query": "beta signup form email collection", "expected_file": "src/components/BetaSignupForm.tsx"},
            {"query": "canvas background WebGL animation", "expected_file": "src/components/CanvasBackground.tsx"},
            {"query": "roadmap section feature timeline", "expected_file": "src/components/EnhancedRoadmapSection.tsx"},
            {"query": "trust section social proof testimonials", "expected_file": "src/components/EnhancedTrustSection.tsx"},
            {"query": "parallax scroll controller animation", "expected_file": "src/components/ParallaxController.tsx"},
            {"query": "footer component layout", "expected_file": "src/components/PercentageBasedFooter.tsx"},
            {"query": "GSAP animation hook useGSAP", "expected_file": "src/hooks/useGSAP.ts"},
            {"query": "responsive media query breakpoints", "expected_file": "src/utils/mediaQueries.ts"},
            {"query": "Next.js root layout metadata", "expected_file": "src/app/layout.tsx"},
            {"query": "homepage main page component", "expected_file": "src/app/page.tsx"},
            {"query": "business landing page", "expected_file": "src/app/business/page.tsx"},
            {"query": "feature cards grid section", "expected_file": "src/components/CardsSection.tsx"},
            {"query": "global CSS styles and Tailwind", "expected_file": "src/styles/globals.css"},
        ],
    },
    "test2-halley": {
        "path": PROJECT_ROOT / "TEST2",
        "language": "TypeScript/React",
        "queries": [
            {"query": "hero section landing page marketing", "expected_file": "website.clean/components/sections/HeroSection.tsx"},
            {"query": "how it works feature walkthrough steps", "expected_file": "website.clean/components/sections/HowItWorks.tsx"},
            {"query": "comparison grid table features versus", "expected_file": "website.clean/components/sections/ComparisonGrid.tsx"},
            {"query": "call to action CTA button section", "expected_file": "website.clean/components/sections/CTASection.tsx"},
            {"query": "system requirements minimum specs hardware", "expected_file": "website.clean/components/sections/SystemRequirements.tsx"},
            {"query": "footer links navigation bottom page", "expected_file": "website.clean/components/sections/Footer.tsx"},
            {"query": "core features product highlights section", "expected_file": "website.clean/components/sections/CoreFeatures.tsx"},
            {"query": "extended features additional capabilities", "expected_file": "website.clean/components/sections/ExtendedFeatures.tsx"},
            {"query": "header navigation top bar logo", "expected_file": "website.clean/components/layout/Header.tsx"},
            {"query": "privacy policy legal page content", "expected_file": "website.clean/app/privacy/page.tsx"},
            {"query": "download page portal app purchase", "expected_file": "website.clean/app/download/page.tsx"},
            {"query": "main homepage landing page layout", "expected_file": "website.clean/app/page.tsx"},
            {"query": "3D heart scene three.js WebGL", "expected_file": "website.clean/components/three/HeartScene.tsx"},
            {"query": "copy content text strings marketing", "expected_file": "website.clean/content/copy.ts"},
        ],
    },
    "test3-jezebel": {
        "path": PROJECT_ROOT / "TEST3",
        "language": "Python/TypeScript/Swift",
        "queries": [
            {"query": "music player screen audio playback controls", "expected_file": "mobile/src/screens/PlayerScreen.tsx"},
            {"query": "DJ sets playlist collection screen", "expected_file": "mobile/src/screens/DJSetsScreen.tsx"},
            {"query": "authentication context user login state provider", "expected_file": "mobile/src/contexts/AuthContext.tsx"},
            {"query": "app navigation routes stack screens", "expected_file": "mobile/src/navigation/AppNavigator.tsx"},
            {"query": "tab navigator bottom bar screen tabs", "expected_file": "mobile/src/navigation/TabNavigator.tsx"},
            {"query": "playback state store audio session", "expected_file": "mobile/src/state/playbackStore.ts"},
            {"query": "music types interfaces track album artist", "expected_file": "mobile/src/types/music.ts"},
            {"query": "FastAPI server main application routes", "expected_file": "backend/src/api_server.py"},
            {"query": "Spotify API integration OAuth token", "expected_file": "backend/src/api/spotify.py"},
            {"query": "Apple Music API integration MusicKit", "expected_file": "backend/src/api/apple_music.py"},
            {"query": "audio analysis AI processing features", "expected_file": "backend/src/ai/audio_analysis.py"},
            {"query": "recommendation engine AI music suggestions", "expected_file": "backend/src/ai/recommendation_engine.py"},
            {"query": "rate limiting middleware request throttle", "expected_file": "backend/src/middleware/rate_limiting.py"},
            {"query": "Firebase cloud functions triggers events", "expected_file": "functions/src/index.ts"},
            {"query": "welcome onboarding screen first launch", "expected_file": "mobile/src/screens/WelcomeScreen.tsx"},
            {"query": "library screen music collection browse", "expected_file": "mobile/src/screens/LibraryScreen.tsx"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Doc-only ground truth (queries targeting documentation files)
# Only repos with meaningful doc content are included.
# ---------------------------------------------------------------------------

DOC_INCLUDE_GLOBS = ["**/*.md", "**/*.markdown", "**/*.rst", "**/*.txt", "**/*.adoc"]

DOC_QUERIES: Dict[str, List[Dict[str, str]]] = {
    "cobra": [
        {"query": "how to create root command and add subcommands to CLI application", "expected_file": "site/content/user_guide.md"},
        {"query": "configure bash shell completion for command line tool", "expected_file": "site/content/completions/bash.md"},
        {"query": "set up zsh shell completion integration", "expected_file": "site/content/completions/zsh.md"},
        {"query": "powershell tab completion for CLI commands", "expected_file": "site/content/completions/powershell.md"},
        {"query": "fish shell completion configuration", "expected_file": "site/content/completions/fish.md"},
        {"query": "active help hints and warnings during tab completion", "expected_file": "site/content/active_help.md"},
        {"query": "generate markdown documentation from cobra commands", "expected_file": "site/content/docgen/md.md"},
        {"query": "generate unix man page documentation from commands", "expected_file": "site/content/docgen/man.md"},
        {"query": "popular projects and tools that use cobra library", "expected_file": "site/content/projects_using_cobra.md"},
    ],
    "got": [
        {"query": "quick start guide getting started making HTTP requests", "expected_file": "documentation/quick-start.md"},
        {"query": "promise based API usage for making HTTP requests", "expected_file": "documentation/1-promise.md"},
        {"query": "request configuration options URL headers method body", "expected_file": "documentation/2-options.md"},
        {"query": "streaming API download upload duplex progress events", "expected_file": "documentation/3-streams.md"},
        {"query": "automatic pagination traverse paginated API endpoints", "expected_file": "documentation/4-pagination.md"},
        {"query": "HTTPS TLS SSL certificate trust configuration", "expected_file": "documentation/5-https.md"},
        {"query": "timeout settings for connection socket send response", "expected_file": "documentation/6-timeout.md"},
        {"query": "retry strategy exponential backoff status codes limits", "expected_file": "documentation/7-retry.md"},
        {"query": "error types HTTP request cancel timeout errors", "expected_file": "documentation/8-errors.md"},
        {"query": "hooks lifecycle events beforeRequest afterResponse init", "expected_file": "documentation/9-hooks.md"},
        {"query": "create custom got instances with shared defaults", "expected_file": "documentation/10-instances.md"},
    ],
    "click": [
        {"query": "password option hidden prompt confirmation input decorator", "expected_file": "docs/option-decorators.md"},
        {"query": "testing CLI applications CliRunner invoke result output", "expected_file": "docs/testing.md"},
        {"query": "shell tab completion bash zsh fish setup configuration", "expected_file": "docs/shell-completion.md"},
        {"query": "parameter types choice file path integer range tuple", "expected_file": "docs/parameter-types.md"},
        {"query": "quickstart tutorial create first click command", "expected_file": "docs/quickstart.md"},
        {"query": "exception handling abort usage error formatting", "expected_file": "docs/exceptions.md"},
        {"query": "unicode text encoding support terminal output", "expected_file": "docs/unicode-support.md"},
        {"query": "complex applications multiple commands plugins lazy loading", "expected_file": "docs/complex.md"},
        {"query": "commands and groups nested subcommands organization", "expected_file": "docs/commands-and-groups.rst"},
        {"query": "frequently asked questions Windows colors terminal", "expected_file": "docs/faqs.md"},
    ],
    "gin": [
        {"query": "gin web framework features installation getting started", "expected_file": "README.md"},
        {"query": "API examples routes JSON binding middleware usage", "expected_file": "docs/doc.md"},
        {"query": "benchmark performance comparison speed latency", "expected_file": "BENCHMARKS.md"},
        {"query": "contributing guidelines pull request code review", "expected_file": "CONTRIBUTING.md"},
    ],
    "chi": [
        {"query": "chi lightweight composable HTTP router middleware Go", "expected_file": "README.md"},
        {"query": "REST API routes endpoint example documentation", "expected_file": "_examples/rest/routes.md"},
        {"query": "changelog version history releases updates", "expected_file": "CHANGELOG.md"},
    ],
    "slim": [
        {"query": "slim PHP micro framework PSR-7 HTTP application", "expected_file": "README.md"},
        {"query": "upgrading migration guide breaking changes versions", "expected_file": "UPGRADING.md"},
        {"query": "changelog releases version history PHP", "expected_file": "CHANGELOG.md"},
    ],
    "hanami": [
        {"query": "hanami router ruby web framework setup usage", "expected_file": "README.md"},
        {"query": "changelog version releases updates ruby", "expected_file": "CHANGELOG.md"},
    ],
    "test-nextjs": [
        {"query": "hero section design plan upgrade animation", "expected_file": "docs/DesignPlan/1-hero.md"},
        {"query": "overall upgrade plan site redesign strategy", "expected_file": "docs/DesignPlan/0-overall-upgrad-plan.md"},
        {"query": "trust section parallax scroll redesign layout", "expected_file": "docs/DesignPlan/4-Updated-Trust-paralax.md"},
        {"query": "site roadmap timeline features milestones", "expected_file": "docs/site_roadmap.md"},
        {"query": "trust section redesign layout testimonials", "expected_file": "docs/trust_section_redesign.md"},
        {"query": "questions for designer feedback review", "expected_file": "docs/questions_for_designer.md"},
    ],
    "test2-halley": [
        {"query": "website plan master strategy marketing landing", "expected_file": "research-docs/01_Initial-planning_concepts/WEBSITE-PLAN.md"},
        {"query": "marketing funnel user journey conversion flow", "expected_file": "research-docs/01_Initial-planning_concepts/MARKETING-FUNNEL.md"},
        {"query": "competitor sites analysis comparison review", "expected_file": "research-docs/01_Initial-planning_concepts/COMPETITOR-SITES.md"},
        {"query": "app alignment product website consistency brand", "expected_file": "research-docs/01_Initial-planning_concepts/APP-ALIGNMENT.md"},
        {"query": "localization translation multi-language website international", "expected_file": "research-docs/10_languages/SITE-LOCALIZATION.md"},
        {"query": "app localization internationalization mobile strategy", "expected_file": "research-docs/10_languages/APP-LOCALIZATION.md"},
        {"query": "payment checkout purchase flow billing", "expected_file": "research-docs/08_payment-infrastructure/CHECKOUT-FLOW.md"},
        {"query": "licensing system activation keys serial numbers", "expected_file": "research-docs/08_payment-infrastructure/LICENSING-SYSTEM.md"},
        {"query": "payment provider comparison processors stripe paddle", "expected_file": "research-docs/08_payment-infrastructure/PROVIDER-COMPARISON.md"},
        {"query": "screenshot plan visual assets marketing images", "expected_file": "research-docs/09_assets-and-media/SCREENSHOT-PLAN.md"},
        {"query": "launch plan go to market release strategy", "expected_file": "research-docs/07_launch-strategy/LAUNCH-PLAN.md"},
        {"query": "beta testing feedback early users program", "expected_file": "research-docs/07_launch-strategy/BETA-TESTING.md"},
    ],
    "test3-jezebel": [
        {"query": "development roadmap timeline milestones phases", "expected_file": "docs/development/development-roadmap.md"},
        {"query": "development guide setup instructions environment", "expected_file": "docs/development/development-guide.md"},
        {"query": "backend requirements API specifications endpoints", "expected_file": "docs/development/backend-requirements.md"},
        {"query": "design system structure components tokens styles", "expected_file": "docs/development/Design-System-Structure.md"},
        {"query": "frontend research UI frameworks mobile comparison", "expected_file": "docs/development/frontend-research.md"},
        {"query": "audio processing requirements analysis features", "expected_file": "docs/development/audio-processing-requirements.md"},
        {"query": "apple music integration todos implementation tasks", "expected_file": "docs/development/apple-music-todos.md"},
        {"query": "spotify integration todos tasks implementation", "expected_file": "docs/development/spotify-todos.md"},
        {"query": "slider UI component design interaction", "expected_file": "docs/development/slider-UI.md"},
        {"query": "quick start guide getting started setup", "expected_file": "docs/QUICK_START_GUIDE.md"},
        {"query": "business plan draft strategy revenue model", "expected_file": "docs/business/business-plan-draft.md"},
        {"query": "app concept overview features vision product", "expected_file": "docs/business/app-concept.md"},
        {"query": "core functionality features requirements specifications", "expected_file": "docs/business/CORE_FUNCTIONALITY.md"},
        {"query": "creator platform content creation tools", "expected_file": "docs/business/CREATOR_PLATFORM.md"},
        {"query": "project overview summary goals objectives", "expected_file": "docs/business/project-overview.md"},
    ],
}


# ---------------------------------------------------------------------------
# Embedding tier factories
# ---------------------------------------------------------------------------

TIERS = {
    "onnx": {
        "label": "nomic-embed-text-v1.5 (ONNX)",
        "factory": lambda: NativeEmbedder(),
    },
    "ollama-text": {
        "label": "nomic-embed-text (Ollama)",
        "factory": lambda: OllamaEmbedder(model="nomic-embed-text"),
    },
    "ollama-code": {
        "label": "nomic-embed-code (Ollama, Matryoshka 768)",
        "factory": lambda: OllamaEmbedder(model="manutic/nomic-embed-code"),
    },
    "v2-moe": {
        "label": "nomic-embed-text-v2-moe (Ollama)",
        "factory": lambda: OllamaEmbedder(model="nomic-embed-text-v2-moe"),
    },
}


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

_FENCED_CODE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
_RST_CODE_RE = re.compile(
    r"\.\.\s+(?:code-block|sourcecode|code|literalinclude)::[^\n]*\n"
    r"(?:[ \t]+:[^\n]*\n)*"       # directive options
    r"\n?"
    r"(?:[ \t]+[^\n]*\n)*",       # indented body
)


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (markdown) and directive blocks (RST)."""
    text = _FENCED_CODE_RE.sub("", text)
    text = _RST_CODE_RE.sub("", text)
    return text


def _default_exclude_globs(extra: Optional[List[str]] = None) -> List[str]:
    """Build standard exclude globs, optionally adding extra patterns."""
    from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
    globs = [f"**/{d}/**" for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES)]
    globs.append("**/.*")
    globs.extend(["**/*.lock", "**/*.log", "**/.DS_Store"])
    if extra:
        globs.extend(extra)
    return globs


def _build_docs_index(
    repo_path: Path,
    idx_dir: Path,
    embedder: Embedder,
    strip_code: bool = False,
) -> None:
    """Build a CodeIndex containing ONLY doc files.

    If strip_code is True, fenced code blocks are removed from doc content
    before indexing so we measure pure natural-language retrieval.
    """
    if strip_code:
        # Copy doc files to temp dir with code blocks stripped
        tmpdir = Path(tempfile.mkdtemp(prefix="codrag_docs_stripped_"))
        try:
            doc_exts = {".md", ".markdown", ".rst", ".txt", ".adoc"}
            for root, dirs, files in os.walk(repo_path):
                # Skip excluded dirs
                dirs[:] = [d for d in dirs if d not in {
                    ".git", ".codrag", "node_modules", "__pycache__",
                    ".tox", "vendor", "dist", "build",
                } and not d.startswith(".")]
                for fname in files:
                    if Path(fname).suffix.lower() not in doc_exts:
                        continue
                    src = Path(root) / fname
                    rel = src.relative_to(repo_path)
                    content = src.read_text(encoding="utf-8", errors="replace")
                    stripped = _strip_code_blocks(content)
                    dest = tmpdir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(stripped, encoding="utf-8")

            exclude = _default_exclude_globs()
            idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
            idx.build(repo_root=tmpdir, include_globs=DOC_INCLUDE_GLOBS, exclude_globs=exclude)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        # Docs-only: include only doc file globs
        exclude = _default_exclude_globs()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo_path, include_globs=DOC_INCLUDE_GLOBS, exclude_globs=exclude)


def _build_trace_index(
    repo_path: Path,
    idx_dir: Path,
    embedder: Embedder,
) -> None:
    """Build a CodeIndex from trace-graph structural data only.

    Steps:
    1. Run TraceBuilder to get symbol spans and relationships.
    2. For each file node, create a synthetic text document containing
       file path, language, and the names/kinds of symbols it contains.
    3. Write these documents to a temp directory and build CodeIndex.
    """
    from codrag.core.trace import TraceBuilder

    idx_dir.mkdir(parents=True, exist_ok=True)
    exclude = _default_exclude_globs(extra=["**/Pods/**", "**/venv/**", "**/fresh_venv/**"])
    tb = TraceBuilder(
        repo_root=repo_path, index_dir=idx_dir,
        exclude_globs=exclude, use_gitignore=True,
    )
    tb.build()

    # Load trace nodes and edges
    trace_nodes: List[Dict[str, Any]] = []
    nodes_path = idx_dir / "trace_nodes.jsonl"
    if nodes_path.exists():
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    trace_nodes.append(json.loads(line))

    trace_edges: List[Dict[str, Any]] = []
    edges_path = idx_dir / "trace_edges.jsonl"
    if edges_path.exists():
        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    trace_edges.append(json.loads(line))

    # Group symbols by file
    file_nodes = {n["id"]: n for n in trace_nodes if n.get("kind") == "file"}
    symbol_nodes = [n for n in trace_nodes if n.get("kind") == "symbol"]

    # Build edge lookup: source → [(relation, target_name)]
    node_by_id = {n["id"]: n for n in trace_nodes}
    file_symbols: Dict[str, List[Dict[str, Any]]] = {}
    for sn in symbol_nodes:
        fp = sn.get("file_path", "")
        file_symbols.setdefault(fp, []).append(sn)

    file_imports: Dict[str, List[str]] = {}
    for edge in trace_edges:
        src_node = node_by_id.get(edge.get("source", ""))
        tgt_node = node_by_id.get(edge.get("target", ""))
        if not src_node or not tgt_node:
            continue
        rel = edge.get("relation", "")
        if rel in ("imports", "uses"):
            src_file = src_node.get("file_path", "")
            tgt_name = tgt_node.get("name", tgt_node.get("id", ""))
            file_imports.setdefault(src_file, []).append(tgt_name)

    # Create synthetic documents
    tmpdir = Path(tempfile.mkdtemp(prefix="codrag_trace_"))
    try:
        for fid, fnode in file_nodes.items():
            rel_path = fnode.get("file_path", "")
            if not rel_path:
                continue
            lang = fnode.get("language", "unknown")
            lines: List[str] = [
                f"File: {rel_path}",
                f"Language: {lang}",
            ]
            syms = file_symbols.get(rel_path, [])
            if syms:
                lines.append("Symbols:")
                for s in syms:
                    sk = s.get("symbol_kind", "symbol")
                    sn_name = s.get("name", "?")
                    span = s.get("span", {})
                    span_str = ""
                    if span:
                        span_str = f" (lines {span.get('start_line', '?')}-{span.get('end_line', '?')})"
                    lines.append(f"  - {sk}: {sn_name}{span_str}")

            imps = file_imports.get(rel_path, [])
            if imps:
                lines.append(f"Imports: {', '.join(sorted(set(imps)))}")

            # Write as a .md file so CodeIndex treats it as documentation
            dest = tmpdir / (rel_path + ".trace.md")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("\n".join(lines), encoding="utf-8")

        exclude = _default_exclude_globs()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=tmpdir, include_globs=["**/*.trace.md"], exclude_globs=exclude)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def eval_repo(
    repo_name: str,
    repo_cfg: Dict[str, Any],
    embedder: Embedder,
    tier_label: str,
    verbose: bool = False,
    docs_only: bool = False,
    strip_code: bool = False,
    trace_only: bool = False,
) -> Dict[str, Any]:
    """Build index and evaluate queries for a single repo + tier."""
    repo_path = repo_cfg["path"]

    # Select ground truth: doc queries for docs-only modes, code queries otherwise
    if docs_only or strip_code:
        queries = DOC_QUERIES.get(repo_name, [])
        if not queries:
            return {
                "repo": repo_name, "language": repo_cfg["language"],
                "tier": tier_label, "chunks": 0, "build_time_s": 0,
                "queries": 0, "recall_at_1": 0, "recall_at_3": 0,
                "recall_at_5": 0, "mrr": 0, "misses": [], "details": [],
                "mode": "docs-only" if docs_only else "strip-code",
                "skipped": "no doc queries for this repo",
            }
    else:
        queries = repo_cfg["queries"]

    # Build index
    suffix = tier_label.replace(' ', '_').replace('/', '_')
    if strip_code:
        suffix += "_strip_code"
    elif docs_only:
        suffix += "_docs_only"
    elif trace_only:
        suffix += "_trace_only"
    idx_dir = repo_path / ".codrag" / f"eval_{suffix}"
    if idx_dir.exists():
        shutil.rmtree(idx_dir)

    t0 = time.perf_counter()

    if trace_only:
        _build_trace_index(repo_path, idx_dir, embedder)
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx._load()
    elif docs_only or strip_code:
        _build_docs_index(repo_path, idx_dir, embedder, strip_code=strip_code)
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx._load()
    else:
        exclude = _default_exclude_globs(extra=["**/Pods/**", "**/venv/**", "**/fresh_venv/**"])
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo_path, exclude_globs=exclude, use_gitignore=True)

    build_time = time.perf_counter() - t0

    chunk_count = len(idx._documents) if idx._documents else 0

    # Run queries
    results = []
    for gt in queries:
        query = gt["query"]
        expected = gt["expected_file"]

        search_results = idx.search(query, k=10, min_score=0.0)
        files = []
        for sr in search_results[:10]:
            sp = sr.doc.get("source_path", "")
            # In trace-only mode, synthetic docs have .trace.md suffix
            if trace_only and sp.endswith(".trace.md"):
                sp = sp[: -len(".trace.md")]
            files.append((sp, float(sr.score)))

        rank = None
        for i, (fp, _) in enumerate(files):
            if fp == expected and rank is None:
                rank = i + 1

        results.append({
            "query": query,
            "expected": expected,
            "rank": rank,
            "top_result": files[0][0] if files else None,
            "top_score": files[0][1] if files else 0.0,
            "top_3": [(fp, round(sc, 3)) for fp, sc in files[:3]],
        })

    n = len(results)
    recall_1 = sum(1 for r in results if r["rank"] == 1) / n
    recall_3 = sum(1 for r in results if r["rank"] is not None and r["rank"] <= 3) / n
    recall_5 = sum(1 for r in results if r["rank"] is not None and r["rank"] <= 5) / n
    mrr = statistics.mean(
        [1.0 / r["rank"] if r["rank"] is not None else 0.0 for r in results]
    )

    misses = [r for r in results if r["rank"] != 1]

    return {
        "repo": repo_name,
        "language": repo_cfg["language"],
        "tier": tier_label,
        "chunks": chunk_count,
        "build_time_s": round(build_time, 1),
        "queries": n,
        "recall_at_1": recall_1,
        "recall_at_3": recall_3,
        "recall_at_5": recall_5,
        "mrr": mrr,
        "misses": misses,
        "details": results,
    }


def print_result(result: Dict[str, Any], verbose: bool = False) -> None:
    """Print evaluation results for one repo+tier."""
    n = result["queries"]
    r1 = result["recall_at_1"]
    r3 = result["recall_at_3"]
    r5 = result["recall_at_5"]
    print(f"\n  {result['tier']}")
    print(f"    {result['chunks']} chunks, built in {result['build_time_s']}s")
    print(f"    R@1={r1:.0%} ({int(r1*n)}/{n})  R@3={r3:.0%}  R@5={r5:.0%}  MRR={result['mrr']:.3f}")

    if result["misses"]:
        print(f"    Misses ({len(result['misses'])}):")
        for m in result["misses"]:
            rank_s = f"rank={m['rank']}" if m["rank"] else "NOT IN TOP 10"
            print(f"      Q: {m['query']!r}")
            print(f"        Expected: {m['expected']}  Got: {m['top_result']}  ({rank_s})")
            if verbose:
                for fp, sc in m["top_3"]:
                    marker = " <<<" if fp == m["expected"] else ""
                    print(f"          {sc:.3f}  {fp}{marker}")
    else:
        print(f"    All {n} queries correct!")


def print_summary(all_results: List[Dict[str, Any]]) -> None:
    """Print summary comparison table."""
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    print(f"{'Repo':<15} {'Language':<12} {'Tier':<40} {'R@1':>5} {'R@3':>5} {'R@5':>5} {'MRR':>6}")
    print("-" * 100)
    for r in all_results:
        n = r["queries"]
        print(
            f"{r['repo']:<15} {r['language']:<12} {r['tier']:<40} "
            f"{r['recall_at_1']:>4.0%} {r['recall_at_3']:>4.0%} {r['recall_at_5']:>4.0%} "
            f"{r['mrr']:>6.3f}"
        )
    print("-" * 100)


def main():
    parser = argparse.ArgumentParser(description="Evaluate CoDRAG on real repos")
    parser.add_argument("--repos", nargs="*", default=None,
                        help=f"Repos to evaluate (default: all). Choices: {list(REPOS.keys())}")
    parser.add_argument("--tiers", nargs="*", default=["onnx"],
                        help=f"Tiers to test (default: onnx). Use 'all' for all tiers. Choices: {list(TIERS.keys())}")
    parser.add_argument("--verbose", action="store_true", help="Show top-3 for all misses")
    parser.add_argument("--output", type=Path, default=None, help="Save results as JSON")
    parser.add_argument("--docs-only", action="store_true",
                        help="Index ONLY doc files (.md, .rst, .txt) — test language retrieval")
    parser.add_argument("--strip-code", action="store_true",
                        help="Like --docs-only but strip fenced code blocks from docs first")
    parser.add_argument("--trace-only", action="store_true",
                        help="Index ONLY trace-graph structural data (file/symbol metadata)")
    args = parser.parse_args()

    repo_names = args.repos or list(REPOS.keys())
    tier_names = list(TIERS.keys()) if "all" in args.tiers else args.tiers

    # Validate
    for rn in repo_names:
        if rn not in REPOS:
            print(f"ERROR: Unknown repo {rn!r}. Choices: {list(REPOS.keys())}", file=sys.stderr)
            sys.exit(1)
        if not REPOS[rn]["path"].exists():
            print(f"ERROR: Repo path not found: {REPOS[rn]['path']}", file=sys.stderr)
            sys.exit(1)

    all_results = []

    for rn in repo_names:
        repo_cfg = REPOS[rn]
        print(f"\n{'='*60}")
        print(f"Repo: {rn} ({repo_cfg['language']}) — {repo_cfg['path']}")
        print(f"  {len(repo_cfg['queries'])} ground-truth queries")

        for tn in tier_names:
            tier_cfg = TIERS[tn]
            print(f"\n  Building index with {tier_cfg['label']}...")
            try:
                embedder = tier_cfg["factory"]()
                result = eval_repo(
                    rn, repo_cfg, embedder, tier_cfg["label"], args.verbose,
                    docs_only=args.docs_only, strip_code=args.strip_code,
                    trace_only=args.trace_only,
                )
                if result.get("skipped"):
                    print(f"    SKIPPED: {result['skipped']}")
                    continue
                all_results.append(result)
                print_result(result, verbose=args.verbose)
            except Exception as e:
                import traceback
                print(f"  ERROR: {e}")
                if args.verbose:
                    traceback.print_exc()

    if len(all_results) > 1:
        print_summary(all_results)

    if args.output:
        # Strip non-serializable details for JSON
        save_data = []
        for r in all_results:
            save_data.append({k: v for k, v in r.items() if k != "details"})
        with open(args.output, "w") as f:
            json.dump(save_data, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
