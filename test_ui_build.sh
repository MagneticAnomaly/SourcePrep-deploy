#!/bin/bash
source ~/.nvm/nvm.sh
nvm use
npx turbo run build --filter=@codrag/ui
