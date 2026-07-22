import fs from "fs"
import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig, type Plugin } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

// 写接口中间件：预览服务器运行期内承接网站的名单管理与手动刷新，
// 落盘到 backend/config/watchlist.json（唯一事实源，对话修改也写这里）。
const CONFIG_DIR = path.resolve(__dirname, "../backend/config")
const WATCHLIST = path.join(CONFIG_DIR, "watchlist.json")
const LATEST = path.resolve(__dirname, "public/data/latest.json")

function normalizeCode(raw: string): string | null {
  const m = raw.trim().toUpperCase().replace(/\.HK$/, "")
  if (!/^\d{1,5}$/.test(m)) return null
  return m.padStart(5, "0")
}

function sentinelApi(): Plugin {
  const send = (res: any, obj: unknown, code = 200) => {
    res.statusCode = code
    res.setHeader("Content-Type", "application/json; charset=utf-8")
    res.end(JSON.stringify(obj))
  }
  const readWl = () => JSON.parse(fs.readFileSync(WATCHLIST, "utf-8"))

  return {
    name: "sentinel-api",
    configureServer(server) {
      server.middlewares.use((req: any, res: any, next: any) => {
        const url = req.url?.split("?")[0]
        if (!url?.startsWith("/api/")) return next()

        if (url === "/api/config" && req.method === "GET") {
          try {
            send(res, readWl())
          } catch (e) {
            send(res, { error: String(e) }, 500)
          }
          return
        }

        if (url === "/api/refresh" && req.method === "POST") {
          try {
            const d = JSON.parse(fs.readFileSync(LATEST, "utf-8"))
            d.generatedAt = new Date().toISOString()
            fs.writeFileSync(LATEST, JSON.stringify(d, null, 2))
            send(res, { ok: true, generatedAt: d.generatedAt })
          } catch (e) {
            send(res, { error: String(e) }, 500)
          }
          return
        }

        if (url === "/api/watchlist" && req.method === "POST") {
          let body = ""
          req.on("data", (c: Buffer) => (body += c.toString()))
          req.on("end", () => {
            try {
              const { action, stock } = JSON.parse(body)
              const cfg = readWl()
              const code = normalizeCode(String(stock?.code ?? ""))
              if (!code)
                return send(res, { error: "代码格式应为 1-5 位数字（如 09988 或 700）" }, 400)
              cfg.stocks = cfg.stocks.filter((s: any) => s.code !== code)

              if (action !== "remove") {
                if (!stock?.name?.trim())
                  return send(res, { error: "名称不能为空" }, 400)
                if (stock.cost != null && !(Number(stock.cost) > 0))
                  return send(res, { error: "成本价需为正数" }, 400)
                if (
                  stock.shares != null &&
                  !(Number.isInteger(Number(stock.shares)) && Number(stock.shares) > 0)
                )
                  return send(res, { error: "股数需为正整数" }, 400)

                const hasBands =
                  stock.bands && Number(stock.bands.buyBelow) > 0 && Number(stock.bands.sellAbove) > 0
                cfg.stocks.push({
                  code,
                  windcode: `${code}.HK`,
                  name: stock.name.trim(),
                  cost: stock.cost != null ? Number(stock.cost) : null,
                  shares: stock.shares != null ? Number(stock.shares) : null,
                  bands: hasBands
                    ? stock.bands
                    : {
                        buyBelow: stock.cost ? +(stock.cost * 0.9).toFixed(2) : 0,
                        sellAbove: stock.cost ? +(stock.cost * 1.25).toFixed(2) : 0,
                        stopLoss: null,
                      },
                  thesis: stock.thesis ?? "（待建仓级分析确认）",
                  redLines: stock.redLines ?? ["（待建仓级分析确认）"],
                  bandsStatus: "mock-pending-dossier",
                })
              }
              cfg.updatedAt = new Date().toISOString()
              fs.writeFileSync(WATCHLIST, JSON.stringify(cfg, null, 2))
              send(res, { ok: true, stocks: cfg.stocks })
            } catch (e) {
              send(res, { error: String(e) }, 400)
            }
          })
          return
        }

        send(res, { error: "not found" }, 404)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [inspectAttr(), react(), sentinelApi()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
