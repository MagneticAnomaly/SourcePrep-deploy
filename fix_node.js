const fs = require('fs');

let content = fs.readFileSync('packages/ui/src/components/marketing/MarketingHero.tsx', 'utf8');

// There's a stray '}' in App/page.tsx or MarketingHero? The lint error was in MarketingHero line 823
console.log(content.split('\n').slice(815, 835).join('\n'));

