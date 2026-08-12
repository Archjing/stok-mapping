# stok-mapping 项目架构设计 Slidev 演示稿

文件：`docs/slides/project-architecture/slides.md`

## 本地预览

```bash
npx @slidev/cli docs/slides/project-architecture/slides.md
```

## 导出 PDF

```bash
npx @slidev/cli export docs/slides/project-architecture/slides.md
```

## 维护说明

- 演示稿内容依据 `docs/PROJECT_ARCHITECTURE_OVERVIEW.md` 和 `docs/DEVELOPMENT_PLAN.md` 提炼。
- 当前未修改 `package.json`，避免引入新的 Node 依赖和 lockfile 变动。
- 如需长期维护，可后续增加 `@slidev/cli` 到 `devDependencies`，并补充 npm scripts。
