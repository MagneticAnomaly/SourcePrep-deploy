const fs = require('fs');

// Add UserRole to types.ts
let typesStr = fs.readFileSync('packages/ui/src/types.ts', 'utf8');
if (!typesStr.includes("export type UserRole")) {
  typesStr = typesStr.replace("export type LicenseTier = 'free' | 'pro' | 'team' | 'enterprise';", "export type LicenseTier = 'free' | 'pro' | 'team' | 'enterprise';\n\nexport type UserRole = 'user' | 'admin';\n");
  fs.writeFileSync('packages/ui/src/types.ts', typesStr);
}
