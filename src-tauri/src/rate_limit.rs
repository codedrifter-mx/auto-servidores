use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{Mutex, Semaphore};

pub struct RateLimitGate {
    semaphore: Arc<Semaphore>,
    min_interval: f64,
    last_request: Mutex<Instant>,
    cooldown_until: Mutex<Instant>,
    cooldown_base: f64,
    cooldown_max: f64,
    consecutive_429s: Mutex<u32>,
}

impl RateLimitGate {
    pub fn new(max_concurrent: usize, min_interval: f64, cooldown_base: f64, cooldown_max: f64) -> Self {
        Self {
            semaphore: Arc::new(Semaphore::new(max_concurrent)),
            min_interval,
            last_request: Mutex::new(Instant::now()),
            cooldown_until: Mutex::new(Instant::now()),
            cooldown_base,
            cooldown_max,
            consecutive_429s: Mutex::new(0),
        }
    }

    pub async fn acquire(&self) -> RateLimitPermit {
        let _permit = self.semaphore.clone().acquire_owned().await.unwrap();
        self.wait_if_cooled_down().await;
        self.enforce_min_interval().await;
        RateLimitPermit { _permit }
    }

    pub async fn report_429(&self) -> f64 {
        let mut count = self.consecutive_429s.lock().await;
        *count += 1;
        let cooldown_secs = (self.cooldown_base * 2_f64.powf((*count - 1) as f64))
            .min(self.cooldown_max);
        let cooldown_until = Instant::now() + Duration::from_secs_f64(cooldown_secs);
        *self.cooldown_until.lock().await = cooldown_until;
        cooldown_secs
    }

    pub async fn report_success(&self) {
        *self.consecutive_429s.lock().await = 0;
    }

    async fn wait_if_cooled_down(&self) {
        loop {
            let remaining = {
                let until = self.cooldown_until.lock().await;
                until.saturating_duration_since(Instant::now())
            };
            if remaining.is_zero() {
                break;
            }
            tokio::time::sleep(remaining).await;
        }
    }

    async fn enforce_min_interval(&self) {
        let wait = {
            let mut last = self.last_request.lock().await;
            let now = Instant::now();
            let elapsed = now.saturating_duration_since(*last);
            let min = Duration::from_secs_f64(self.min_interval);
            let wait = min.saturating_sub(elapsed);
            *last = now + wait;
            wait
        };
        if !wait.is_zero() {
            tokio::time::sleep(wait).await;
        }
    }
}

pub struct RateLimitPermit {
    _permit: tokio::sync::OwnedSemaphorePermit,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter_allows_concurrent_within_limit() {
        let gate = RateLimitGate::new(5, 0.0, 5.0, 60.0);
        let mut permits = vec![];
        for _ in 0..5 {
            permits.push(gate.acquire().await);
        }
        assert_eq!(permits.len(), 5);
    }

    #[tokio::test]
    async fn test_report_429_increments_cooldown() {
        let gate = RateLimitGate::new(10, 0.0, 5.0, 60.0);
        let cooldown1 = gate.report_429().await;
        assert_eq!(cooldown1, 5.0);
        let cooldown2 = gate.report_429().await;
        assert_eq!(cooldown2, 10.0);
        gate.report_success().await;
        let cooldown3 = gate.report_429().await;
        assert_eq!(cooldown3, 5.0);
    }

    #[tokio::test]
    async fn test_min_interval_enforcement() {
        let gate = RateLimitGate::new(10, 0.05, 5.0, 60.0);
        let start = Instant::now();
        let _p1 = gate.acquire().await;
        let _p2 = gate.acquire().await;
        let elapsed = start.elapsed();
        assert!(elapsed >= Duration::from_secs_f64(0.04));
    }

    #[tokio::test]
    async fn test_semaphore_limit_blocks() {
        let gate = RateLimitGate::new(2, 0.0, 5.0, 60.0);
        let p1 = gate.acquire().await;
        let p2 = gate.acquire().await;
        let start = Instant::now();
        let acquired = tokio::select! {
            _ = tokio::time::sleep(Duration::from_millis(50)) => false,
            p3 = gate.acquire() => { drop(p3); true },
        };
        drop(p1);
        drop(p2);
        assert!(!acquired || start.elapsed() >= Duration::from_millis(40));
    }

    #[tokio::test]
    async fn test_cooldown_caps_at_max() {
        let gate = RateLimitGate::new(10, 0.0, 5.0, 10.0);
        for _ in 0..10 {
            gate.report_429().await;
        }
        let cooldown = gate.report_429().await;
        assert!(cooldown <= 10.0, "cooldown {} exceeded max 10.0", cooldown);
    }

    #[tokio::test]
    async fn test_success_resets_429_counter() {
        let gate = RateLimitGate::new(10, 0.0, 2.0, 60.0);
        gate.report_429().await;
        gate.report_429().await;
        gate.report_success().await;
        let cooldown = gate.report_429().await;
        assert_eq!(cooldown, 2.0, "cooldown should reset to base after success");
    }
}
