import React, { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import {
  Bell, Bot, ChevronRight, Leaf, Menu, Minus, PackageCheck,
  Plus, Search, ShoppingBag, ShoppingCart, Sparkles, Trash2, X,
} from "lucide-react";
import { api } from "./api";

function Header({ cartCount }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="header">
      <Link className="brand" to="/" aria-label="DELITO home">
        <span className="brand-mark"><Leaf size={21} /></span>
        <span>DELITO</span>
      </Link>
      <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle menu">
        {menuOpen ? <X /> : <Menu />}
      </button>
      <nav className={menuOpen ? "nav open" : "nav"}>
        <NavLink to="/" end onClick={() => setMenuOpen(false)}>Home</NavLink>
        <NavLink to="/catalogue" onClick={() => setMenuOpen(false)}>Groceries</NavLink>
        <NavLink to="/orders" onClick={() => setMenuOpen(false)}>My Orders</NavLink>
        <NavLink to="/notifications" onClick={() => setMenuOpen(false)}><Bell size={18} /></NavLink>
        <NavLink className="cart-link" to="/cart" onClick={() => setMenuOpen(false)}>
          <ShoppingCart size={19} /> Cart
          {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
        </NavLink>
      </nav>
    </header>
  );
}

function ProductCard({ product, onAdd }) {
  const navigate = useNavigate();
  return (
    <article className="product-card">
      <button className="product-image" onClick={() => navigate(`/product/${product.id}`)}>
        <img src={product.image} alt={product.name} />
      </button>
      <div className="product-body">
        <span className="delivery-pill">12 min</span>
        <button className="product-name" onClick={() => navigate(`/product/${product.id}`)}>{product.name}</button>
        <p>{product.unit}</p>
        <div className="product-footer">
          <strong>₹{product.price}</strong>
          <button className="add-button" onClick={() => onAdd(product)}>ADD</button>
        </div>
      </div>
    </article>
  );
}

function Home({ products, onAdd }) {
  const categories = [
    ["Fruits", "🍎"], ["Vegetables", "🥬"], ["Dairy & Eggs", "🥛"],
    ["Bakery", "🥐"], ["Breakfast", "🥣"], ["Pantry", "🫙"],
  ];
  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles size={15} /> Freshness, faster</span>
          <h1>Groceries at your <em>doorstep.</em></h1>
          <p>Handpicked freshness, delivered to you in just minutes.</p>
          <Link className="hero-button" to="/catalogue">Shop groceries <ChevronRight size={18} /></Link>
        </div>
        <div className="hero-art" aria-hidden="true">
          <span>🥦</span><span>🍅</span><span>🥑</span><span>🍊</span>
        </div>
      </section>
      <section className="section">
        <div className="section-heading"><div><span>Shop by</span><h2>Category</h2></div></div>
        <div className="category-grid">
          {categories.map(([name, icon]) => (
            <Link className="category-card" to={`/catalogue?category=${encodeURIComponent(name)}`} key={name}>
              <span>{icon}</span><strong>{name}</strong>
            </Link>
          ))}
        </div>
      </section>
      <section className="section">
        <div className="section-heading"><div><span>Fresh picks</span><h2>Popular now</h2></div>
          <Link to="/catalogue">View all <ChevronRight size={16} /></Link></div>
        <div className="product-grid">
          {products.slice(0, 6).map(product => <ProductCard key={product.id} product={product} onAdd={onAdd} />)}
        </div>
      </section>
    </main>
  );
}

function Catalogue({ products, onAdd }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(new URLSearchParams(window.location.search).get("category") || "");
  const [filtered, setFiltered] = useState(products);

  useEffect(() => {
    const value = search.trim();
    api(`/api/v1/catalogue/products?${new URLSearchParams({
      ...(value ? { search: value } : {}),
      ...(category ? { category } : {}),
    })}`).then(setFiltered).catch(() => setFiltered(products));
  }, [search, category, products]);

  return (
    <main className="page">
      <div className="catalogue-toolbar">
        <div><span className="eyebrow">Fresh & everyday</span><h1>All groceries</h1></div>
        <label className="search-box"><Search size={19} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search groceries" /></label>
      </div>
      <div className="filters">
        {["", "Fruits", "Vegetables", "Dairy & Eggs", "Bakery", "Breakfast", "Pantry"].map(name =>
          <button className={!name || category === name ? "active" : ""} key={name} onClick={() => setCategory(name)}>
            {name || "All"}
          </button>)}
      </div>
      <div className="product-grid">
        {filtered.map(product => <ProductCard key={product.id} product={product} onAdd={onAdd} />)}
      </div>
    </main>
  );
}

function ProductDetails({ products, onAdd }) {
  const { id } = useParams();
  const product = products.find(item => item.id === Number(id));
  if (!product) return <main className="page"><p>Product not found.</p></main>;
  return (
    <main className="page detail-page">
      <div className="detail-image"><img src={product.image} alt={product.name} /></div>
      <div className="detail-info">
        <span className="delivery-pill">Delivery in 12 min</span>
        <h1>{product.name}</h1>
        <p className="detail-unit">{product.unit}</p>
        <strong className="detail-price">₹{product.price}</strong>
        <p>{product.description}</p>
        <h3>Ingredients</h3><p>{product.ingredients}</p>
        <h3>Nutrition</h3>
        <div className="nutrition-grid">
          {Object.entries(product.nutrition).map(([name, value]) =>
            <div key={name}><strong>{value}</strong><span>{name}</span></div>)}
        </div>
        <button className="checkout-button" onClick={() => onAdd(product)}><ShoppingBag size={19} /> Add to basket</button>
      </div>
    </main>
  );
}

function Cart({ cart, onQuantity, onRemove, onClear }) {
  const navigate = useNavigate();
  const items = cart.items || [];
  return (
    <main className="page cart-page">
      <div className="page-title"><span>Your basket</span><h1>Cart</h1></div>
      {items.length === 0 ? (
        <div className="empty-state"><ShoppingCart size={44} /><h2>Your basket is empty</h2><Link to="/catalogue">Start shopping</Link></div>
      ) : (
        <div className="cart-layout">
          <div className="cart-items">
            {items.map(item => (
              <div className="cart-item" key={item.product_id}>
                <img src={item.image} alt={item.name} />
                <div className="cart-item-info"><strong>{item.name}</strong><span>₹{item.price}</span></div>
                <div className="quantity">
                  <button onClick={() => onQuantity(item.product_id, item.quantity - 1)}><Minus size={15} /></button>
                  <span>{item.quantity}</span>
                  <button onClick={() => onQuantity(item.product_id, item.quantity + 1)}><Plus size={15} /></button>
                </div>
                <button className="remove-button" onClick={() => onRemove(item.product_id)} aria-label="Remove"><Trash2 size={18} /></button>
              </div>
            ))}
          </div>
          <aside className="bill">
            <h3>Bill details</h3>
            <div><span>Item total</span><strong>₹{cart.subtotal}</strong></div>
            <div><span>Delivery fee</span><strong>FREE</strong></div>
            <div className="bill-total"><span>To pay</span><strong>₹{cart.subtotal}</strong></div>
            <button className="checkout-button" onClick={() => navigate("/checkout")}>Proceed to checkout</button>
            <button className="text-button" onClick={onClear}>Clear cart</button>
          </aside>
        </div>
      )}
    </main>
  );
}

function Checkout({ cart, onRefresh }) {
  const navigate = useNavigate();
  const [method, setMethod] = useState("Cash on Delivery");
  const [form, setForm] = useState({ customer_name: "", address: "", phone: "" });
  const [placing, setPlacing] = useState(false);

  async function placeOrder(event) {
    event.preventDefault();
    setPlacing(true);
    try {
      await api("/api/v1/orders", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          payment_method: method,
          items: cart.items,
          total: cart.subtotal,
        }),
      });
      await api("/api/v1/cart", { method: "DELETE" });
      await onRefresh();
      navigate("/orders");
    } finally {
      setPlacing(false);
    }
  }

  return (
    <main className="page checkout-page">
      <div className="page-title"><span>Almost there</span><h1>Checkout</h1></div>
      <form className="checkout-layout" onSubmit={placeOrder}>
        <section className="checkout-card">
          <h3>Delivery details</h3>
          <label>Full name<input required value={form.customer_name} onChange={e => setForm({...form, customer_name: e.target.value})} /></label>
          <label>Address<textarea required value={form.address} onChange={e => setForm({...form, address: e.target.value})} /></label>
          <label>Phone number<input required pattern="[0-9]{10}" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} /></label>
          <h3>Payment method</h3>
          {["Cash on Delivery", "Simulated Online Payment"].map(option =>
            <label className="payment-option" key={option}>
              <input type="radio" name="payment" checked={method === option} onChange={() => setMethod(option)} />
              <span>{option}</span>
            </label>)}
        </section>
        <aside className="bill">
          <h3>Order summary</h3>
          <div><span>{cart.item_count || 0} items</span><strong>₹{cart.subtotal}</strong></div>
          <div className="bill-total"><span>Total</span><strong>₹{cart.subtotal}</strong></div>
          <button className="checkout-button" disabled={placing || !cart.items?.length}>
            {placing ? "Placing order..." : "Place order"}
          </button>
        </aside>
      </form>
    </main>
  );
}

function Orders() {
  const [orders, setOrders] = useState([]);
  useEffect(() => { api("/api/v1/orders").then(setOrders).catch(() => setOrders([])); }, []);
  return (
    <main className="page">
      <div className="page-title"><span>Track purchases</span><h1>My Orders</h1></div>
      {orders.length === 0 ? <div className="empty-state"><PackageCheck size={44} /><h2>No orders yet</h2></div> :
        <div className="order-list">{orders.map(order =>
          <article className="order-card" key={order.id}>
            <div><span>{order.id}</span><strong>{order.status}</strong></div>
            <p>{order.items.length} items · ₹{order.total}</p>
            <small>{new Date(order.created_at).toLocaleString()}</small>
          </article>)}</div>}
    </main>
  );
}

function Notifications() {
  const [items, setItems] = useState([]);
  useEffect(() => { api("/api/v1/notifications").then(setItems).catch(() => setItems([])); }, []);
  return (
    <main className="page">
      <div className="page-title"><span>Stay updated</span><h1>Notifications</h1></div>
      {items.length === 0 ? <div className="empty-state"><Bell size={44} /><h2>No notifications</h2></div> :
        <div className="notification-list">{items.map(item =>
          <article key={item.id}><span className="notification-icon"><Bell size={18} /></span>
            <div><strong>{item.title}</strong><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></div></article>)}</div>}
    </main>
  );
}

function Chatbot() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [typing, setTyping] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! I'm DELITO AI, your smart grocery assistant. Ask me anything about products, ingredients, nutrition, or recipes. I'm here to help!" },
  ]);
  const sessionId = "delito-web";

  async function send(text) {
    const value = text || message.trim();
    if (!value) return;
    setMessages(current => [...current, { role: "customer", text: value }]);
    setMessage("");
    setTyping(true);
    try {
      const data = await api("/api/v1/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: value, session_id: sessionId }),
      });
      setMessages(current => [...current, { role: "assistant", text: data.answer }]);
    } catch (error) {
      setMessages(current => [...current, { role: "assistant", text: "DELITO AI is temporarily unavailable. Please try again shortly." }]);
    } finally {
      setTyping(false);
    }
  }

  return (
    <>
      {open && (
        <section className="chat-window">
          <header><span className="chat-logo"><Bot size={20} /></span><div><strong>Ask DELITO AI</strong><small><i /> Online</small></div><button onClick={() => setOpen(false)}><X size={18} /></button></header>
          <div className="chat-messages">
            {messages.map((item, index) => <div className={`chat-bubble ${item.role}`} key={index}>{item.text}</div>)}
            {typing && <div className="typing"><i /><i /><i /></div>}
            {messages.length === 1 && <div className="suggestions">
              {["Which breakfast is high in protein?", "Compare apples and bananas", "Suggest ingredients for a salad"].map(text =>
                <button key={text} onClick={() => send(text)}>{text}</button>)}
            </div>}
          </div>
          <form onSubmit={event => { event.preventDefault(); send(); }}>
            <input value={message} onChange={e => setMessage(e.target.value)} placeholder="Ask about groceries..." />
            <button type="submit" aria-label="Send"><ChevronRight size={19} /></button>
          </form>
        </section>
      )}
      <button className="chat-fab" onClick={() => setOpen(!open)} aria-label="Open DELITO AI"><Bot size={25} /></button>
    </>
  );
}

export default function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({ items: [], subtotal: 0, item_count: 0 });

  async function refreshCart() {
    try { setCart(await api("/api/v1/cart")); } catch { setCart({ items: [], subtotal: 0, item_count: 0 }); }
  }

  useEffect(() => {
    api("/api/v1/catalogue/products").then(setProducts).catch(() => setProducts([]));
    refreshCart();
  }, []);

  async function addToCart(product) {
    const result = await api("/api/v1/cart", {
      method: "POST",
      body: JSON.stringify({ product_id: product.id, name: product.name, price: product.price, image: product.image, quantity: 1 }),
    });
    setCart(result);
  }

  async function changeQuantity(productId, quantity) {
    if (quantity < 1) return removeItem(productId);
    setCart(await api(`/api/v1/cart/${productId}?quantity=${quantity}`, { method: "PATCH" }));
  }

  async function removeItem(productId) {
    setCart(await api(`/api/v1/cart/${productId}`, { method: "DELETE" }));
  }

  async function clearCart() {
    setCart(await api("/api/v1/cart", { method: "DELETE" }));
  }

  return (
    <>
      <Header cartCount={cart.item_count} />
      <Routes>
        <Route path="/" element={<Home products={products} onAdd={addToCart} />} />
        <Route path="/catalogue" element={<Catalogue products={products} onAdd={addToCart} />} />
        <Route path="/product/:id" element={<ProductDetails products={products} onAdd={addToCart} />} />
        <Route path="/cart" element={<Cart cart={cart} onQuantity={changeQuantity} onRemove={removeItem} onClear={clearCart} />} />
        <Route path="/checkout" element={<Checkout cart={cart} onRefresh={refreshCart} />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/notifications" element={<Notifications />} />
      </Routes>
      <Chatbot />
    </>
  );
}
