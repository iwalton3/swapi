var api = new SimpleWebAPI("https://iwalton.com/spa-api");
var login = {};

(async function() {
await api.genMethods();
login = await api.check_user();

const PageTemplate = (props) => <div><div className="titlecontainer"><h1><a className="title" href="/"><img src="/theme/logo.svg" />Ian's Web Server</a></h1>
<div id="subtitle"><h3><a href="#">SPA Test</a> - {props.title}</h3></div>
</div><div id="pagecontent">{props.children}</div></div>

function UserTools(props){
  async function doLogoff(){
    await api.logoff();
    login = await api.check_user();
    triggerRoute();
  }
  async function doLogoffAll(){
    await api.logoff_all();
    login = await api.check_user();
    triggerRoute();
  }
  return <div>
    <br/><h3>Account</h3>
    {props.login.authenticated
      ? (
          <div><p>Welcome, {props.login.user}!</p>
          <p><img src="/theme/leave.png"/> <a id="logoff" onClick={doLogoff}>Log Off</a></p>
          <p><img src="/theme/leave.png"/> <a id="logoffall" onClick={doLogoffAll}>Log Off All Browsers</a></p>
          {login.capabilities.includes("accountmanager")
            ? <p><img src="/theme/user.png"/>  <a href="#manage_users">Manage Users</a></p>
            : ''
          }
          </div>
      ) : (
        <div>
        <p>You are not logged in.</p>
        <p><img src="/theme/user.png"/> <a id="login" href="#login">log in</a></p>
        </div> 
      )}
  </div>
}

routes.default = async function(data) {
  return <PageTemplate title="Main Page">
      <p>Welcome to the simple SPA test! This is an example of a single page web application, using React, SimpleWebAPI, and SimpleRouter. This example application implements authentication via email and authorization through a roles system.</p>
      <UserTools login={login} />
    </PageTemplate>
}



routes.login = async function(data) {
  async function sendEmail(event) {
    event.preventDefault();
    var email = event.target.elements.email.value;
    await api.send_otp(email);
    setView("login_confirm", {"email":email});
  }
  return <PageTemplate title="Login">
      <form onSubmit={sendEmail}>
      <p>Please enter your email address to proceed.</p>
      <label>Email Address: <input key="email" type="text" name="email"/></label>
      <br/><input type="submit" value="Next"/></form>
    </PageTemplate>
}

routes.login_confirm = async function(data) {
  async function doLogin(event) {
    event.preventDefault();
    await api.login(data.email,event.target.elements.token.value);
    login = await api.check_user();
    setView("", {});
  }
  return <PageTemplate title="Login">
      <form onSubmit={doLogin}>
      <p>You should have recieved an email with a single-use login code. Enter it below.</p>
      <label>Email Address: <input key="emailLocked" name="email" value={data.email} disabled/></label> 
      <br/><label>Login Code: <input type="text" name="token"/></label>
      <br/><input type="submit" value="Login"/></form>
    </PageTemplate>
}

const SelectBox = ({options, ...props}) => <select {...props}>
    {options.map((option) => (
      <option key={option}>
        {option}
      </option>
    ))}
  </select>

class UserManager extends React.Component {
  state = { roles: [], users: [] }
  async componentWillMount() {
    var [users, roles] = await Promise.all([api.get_all_users(), api.list_roles()]);
    this.setState({
      roles: roles,
      users: users
    });
  }
  async updateUserList() {
    var users = await api.get_all_users();
    this.setState({
      users: users
    });
  }
  async doAddUser(event) {
    event.preventDefault();
    var ev = event.target.elements;
    await api.register_user(ev.email.value, ev.role.value);
    await this.updateUserList();
  }
  async doChangeUser(event) {
    event.preventDefault();
    var ev = event.target.elements;
    await api.set_user_role(ev.email.value, ev.role.value);
    await this.updateUserList();
  }
  render() {
    return <div>
      <p>This page allows you to manage the user roles for this service.</p>
      <br/><h3>User Listing</h3>
      <table border="1">
        <thead>
        <tr>
        <th>User</th>
        <th>Role</th>
        </tr>
        </thead>
        <tbody>
        {this.state.users.map((row) => (
          <tr key={row.id}>
          <td>{row.username}</td>
          <td>{row.role}</td>
          </tr>
        ))}
        </tbody>
      </table>
      <br/><h3>Add User</h3>
      <form onSubmit={this.doAddUser.bind(this)}>
      <label>User: <input type="text" name="email"/></label><br/>
      <label>Role: <SelectBox name="role" options={this.state.roles}/></label>
      <br/><input type="submit" value="Add"/>
      </form>
      <br/><h3>Change User Role</h3>
      <form onSubmit={this.doChangeUser.bind(this)}>
      <label>User: <SelectBox name="email" options={this.state.users.map(i => i.username)}/></label><br/>
      <label>Role: <SelectBox name="role" options={this.state.roles}/></label>
      <br/><input type="submit" value="Change"/>
      </form>
    </div>
  }
}

routes.manage_users = async function(data) {
  return <PageTemplate title="Manage Users">
    <UserManager/>
  </PageTemplate>
}

triggerRoute();

})();
