#![allow(missing_docs)]

use rust_contract_checks::contract;

#[derive(Debug, Clone, PartialEq, Eq)]
enum DivideError {
    DivisionByZero,
}

#[contract(
    pre(divisor != 0, "0で割る入力は許可しない"),
    post(*ret * divisor == dividend, "戻り値から元の被除数を復元できる"),
    error(matches!(err, DivideError::DivisionByZero), "0除算のみ許可する"),
    pure("入力以外の状態に依存しない"),
    panic_free("契約違反以外ではpanicしない")
)]
fn divide(dividend: i32, divisor: i32) -> Result<i32, DivideError> {
    if divisor == 0 {
        return Err(DivideError::DivisionByZero);
    }

    Ok(dividend / divisor)
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum BudgetError {
    InvalidAmount,
    Overdraft,
}

#[derive(Debug)]
struct Budget {
    remaining: i32,
}

impl Budget {
    #[contract(
        invariant(self.remaining >= 0, "残高は常に0以上"),
        error(
            matches!(err, BudgetError::InvalidAmount | BudgetError::Overdraft),
            "定義済みの失敗のみ返す"
        )
    )]
    fn spend(&mut self, amount: i32) -> Result<(), BudgetError> {
        if amount < 0 {
            return Err(BudgetError::InvalidAmount);
        }

        if amount > self.remaining {
            return Err(BudgetError::Overdraft);
        }

        self.remaining -= amount;
        Ok(())
    }
}

fn main() {
    assert_eq!(divide(12, 3), Ok(4));

    let mut budget = Budget { remaining: 10 };
    assert_eq!(budget.spend(3), Ok(()));
    assert_eq!(budget.remaining, 7);
}
