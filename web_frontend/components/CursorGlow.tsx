"use client"

import { useEffect, useRef } from "react"

export function CursorGlow() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let mouseX = -500, mouseY = -500
    let targetX = -500, targetY = -500
    let hue = 215
    let raf: number
    let particles: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; size: number }[] = []

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener("resize", resize)

    const onMouseMove = (e: MouseEvent) => {
      targetX = e.clientX
      targetY = e.clientY

      // Spawn particles on movement
      const speed = Math.sqrt(
        Math.pow(e.movementX, 2) + Math.pow(e.movementY, 2)
      )
      if (speed > 3 && particles.length < 40) {
        particles.push({
          x: e.clientX,
          y: e.clientY,
          vx: (Math.random() - 0.5) * 1.5,
          vy: (Math.random() - 0.5) * 1.5,
          life: 1,
          maxLife: 0.6 + Math.random() * 0.6,
          size: 1.5 + Math.random() * 2,
        })
      }
    }

    window.addEventListener("mousemove", onMouseMove)

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Smooth follow
      mouseX += (targetX - mouseX) * 0.12
      mouseY += (targetY - mouseY) * 0.12

      // Slowly shift hue
      hue = (hue + 0.15) % 360

      // Main glow orb — large ambient light
      const grad = ctx.createRadialGradient(mouseX, mouseY, 0, mouseX, mouseY, 350)
      grad.addColorStop(0, `hsla(${hue}, 100%, 65%, 0.07)`)
      grad.addColorStop(0.3, `hsla(${hue + 30}, 90%, 55%, 0.03)`)
      grad.addColorStop(0.6, `hsla(${hue + 60}, 80%, 50%, 0.01)`)
      grad.addColorStop(1, "transparent")
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Inner bright core
      const core = ctx.createRadialGradient(mouseX, mouseY, 0, mouseX, mouseY, 80)
      core.addColorStop(0, `hsla(${hue}, 100%, 70%, 0.12)`)
      core.addColorStop(0.5, `hsla(${hue + 20}, 100%, 60%, 0.04)`)
      core.addColorStop(1, "transparent")
      ctx.fillStyle = core
      ctx.fillRect(mouseX - 100, mouseY - 100, 200, 200)

      // Update and draw particles
      particles = particles.filter(p => p.life > 0)
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        p.life -= 1 / 60 / p.maxLife
        p.vx *= 0.98
        p.vy *= 0.98

        const alpha = Math.max(0, p.life) * 0.4
        const r = Math.max(0.1, p.size * p.life)
        ctx.beginPath()
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
        ctx.fillStyle = `hsla(${hue + Math.random() * 40}, 100%, 70%, ${alpha})`
        ctx.fill()
      }

      raf = requestAnimationFrame(animate)
    }

    raf = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("resize", resize)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[1]"
      style={{ mixBlendMode: "screen" }}
    />
  )
}
