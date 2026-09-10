import streamlit as st
import edu_db
import razorpay

def render(user_info):
    st.markdown("<h1 style='color:#f8fafc;'>💳 Top-Up Wallet</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8;'>Add funds to your virtual wallet to unlock premium features, microtransactions, and international stocks.</p>", unsafe_allow_html=True)

    progress = edu_db.load_progress()
    quest_coins = int(progress.get("quest_coins", 0))
    virtual_balance = float(progress.get("virtual_balance", 15000.0))

    # Check if we just returned from a successful payment
    if st.query_params.get("success") == "true":
        # Check if we already credited this session to avoid double-crediting on refresh
        if not st.session_state.get("payment_credited", False):
            # Try to get the exact amount from the URL to avoid session state loss issues
            url_amt = st.query_params.get("amt")
            if url_amt:
                amount_paid_inr = float(url_amt)
            else:
                amount_paid_inr = st.session_state.get("pending_payment_amount", 500.0)
                
            coins_awarded = int(amount_paid_inr * 10)  # 10x Multiplier!
            
            progress["quest_coins"] = quest_coins + coins_awarded
            edu_db.save_progress(progress)
            
            st.session_state.payment_credited = True
            st.session_state.pending_payment_amount = 0.0
            quest_coins = progress["quest_coins"]
            
            st.balloons()
            st.success(f"🎉 Payment Successful! You received {coins_awarded:,} Quest Coins!")
            
            # INSTANTLY wipe the URL parameters so hard refresh doesn't trigger this again!
            st.query_params.pop("success", None)
            st.query_params.pop("amt", None)
        else:
            st.success("Payment already processed.")
            st.query_params.pop("success", None)
            st.query_params.pop("amt", None)

    st.markdown(f"### 🪙 Quest Coins: <span style='color:#fbbf24;'>{quest_coins:,}</span>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size: 0.9rem; color:#94a3b8;'><em>(Virtual Trading Balance: ₹ {virtual_balance:,.0f})</em></p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### Buy Quest Coins")
    st.markdown("<p style='font-size: 0.9rem; color:#94a3b8;'>Use Quest Coins to unlock Discord Nitro Themes, US Stocks, and Premium Badges!</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center;'>Starter</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#38bdf8;'>5,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:#94a3b8;'>for ₹ 500</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 500", key="buy_500", use_container_width=True):
                _create_payment_link(500, user_info)

    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center;'>Pro</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#a855f7;'>10,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:#94a3b8;'>for ₹ 1,000</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 1,000", key="buy_1000", type="primary", use_container_width=True):
                _create_payment_link(1000, user_info)

    with col3:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center;'>Whale</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#fbbf24;'>50,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:#94a3b8;'>for ₹ 5,000</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 5,000", key="buy_5000", use_container_width=True):
                _create_payment_link(5000, user_info)


def _create_payment_link(amount_inr, user_info):
    try:
        # Initialize Razorpay Client with provided test keys
        client = razorpay.Client(auth=("rzp_test_TaNK4SlVzf5jfB", "9vb4dFfdUSxs9sZ9PH66XMDc"))

        # Setup redirect URL
        # For localhost testing, we use localhost:8501
        redirect_url = f"http://localhost:8501/?workspace=education&page=Wallet&success=true&amt={amount_inr}"

        data = {
            "amount": amount_inr * 100, # Razorpay expects paise (multiply by 100)
            "currency": "INR",
            "description": f"Top-Up QUEST Wallet (₹{amount_inr})",
            "customer": {
                "name": user_info.get("display_name", "Test User"),
                "email": user_info.get("email", "test@example.com"),
                "contact": "9876543210"
            },
            "notify": {
                "sms": False,
                "email": False
            },
            "reminder_enable": False,
            "callback_url": redirect_url,
            "callback_method": "get"
        }

        # Save pending amount in session state to credit upon return
        st.session_state.pending_payment_amount = float(amount_inr)
        st.session_state.payment_credited = False

        # Generate link
        payment_link = client.payment_link.create(data)
        checkout_url = payment_link.get("short_url")
        
        if checkout_url:
            st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
            st.info(f"Redirecting to secure Razorpay checkout... [Click here if not redirected]({checkout_url})")
            
    except Exception as e:
        st.error(f"Failed to create payment link: {str(e)}")
