// Expo + pnpm monorepo Metro config.
// Hoisted lookup is disabled so Metro doesn't accidentally resolve a
// package from a sibling app's node_modules. watchFolders includes the
// workspace root so packages/ui and packages/api edits trigger reloads.
const { getDefaultConfig } = require('expo/metro-config')
const path = require('path')

const projectRoot = __dirname
const workspaceRoot = path.resolve(projectRoot, '../..')

const config = getDefaultConfig(projectRoot)
config.watchFolders = [workspaceRoot]
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
]
config.resolver.disableHierarchicalLookup = true

module.exports = config
