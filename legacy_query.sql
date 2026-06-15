-- Legacy-система: учёт заказов и задолженности клиентов
-- (исходный код из тестового задания, Часть 2)

CREATE TABLE Orders (
    Id INT PRIMARY KEY,
    CustomerName NVARCHAR(100),
    Amount DECIMAL(10,2),
    Status NVARCHAR(50),
    CreatedAt DATETIME
);

CREATE TABLE Payments (
    Id INT PRIMARY KEY,
    OrderId INT,
    PaidAmount DECIMAL(10,2),
    PaidAt DATETIME
);

-- Отчёт о задолженности: заказы, по которым клиент недоплатил
SELECT
    o.Id,
    o.CustomerName,
    o.Amount,
    ISNULL(SUM(p.PaidAmount),0) as Paid,
    o.Amount - ISNULL(SUM(p.PaidAmount),0) as Debt
FROM Orders o
LEFT JOIN Payments p ON p.OrderId = o.Id
WHERE o.Status != 'Cancelled'
GROUP BY o.Id, o.CustomerName, o.Amount
HAVING o.Amount - ISNULL(SUM(p.PaidAmount),0) > 0
